try:
    from threading import Lock
except ImportError:
    from dummy_threading import Lock

from cpython.pycapsule cimport PyCapsule_New

import numpy as np

from randomgen.common cimport *
from randomgen.distributions cimport bitgen_t
from randomgen.entropy import random_entropy, seed_by_array

__all__ = ['ChaCha']

np.import_array()

cdef extern from "src/chacha/chacha.h":

    struct CHACHA_STATE_T:
        uint32_t block[16]
        uint32_t keysetup[8]
        uint64_t ctr[2]
        int rounds;

    ctypedef CHACHA_STATE_T chacha_state_t

    uint32_t chacha_next32(chacha_state_t *state) nogil
    uint64_t chacha_next64(chacha_state_t *state) nogil
    double chacha_next_double(chacha_state_t *state) nogil

    void chacha_advance(chacha_state_t *state, uint64_t *delta)

cdef uint64_t chacha_uint64(void* st) nogil:
    return chacha_next64(<chacha_state_t *>st)

cdef uint32_t chacha_uint32(void *st) nogil:
    return chacha_next32(<chacha_state_t *> st)

cdef double chacha_double(void* st) nogil:
    return chacha_next_double(<chacha_state_t *>st)

cdef class ChaCha:
    """
    ChaCha(seed=None)

    Container for the ChaCha family of Counter pseudo-random number generators

    Parameters
    ----------
    seed : {None, int}, optional
        Random seed initializing the pseudo-random number generator.
        Can be an integer in [0, 2**256-1], an array of 4 uint64 values
        or ``None`` (the default). If `seed` is ``None``, then  data is read
        from ``/dev/urandom`` (or the Windows analog) if available.  If
        unavailable, a hash of the time and process ID is used.
    counter : {None, int, array_like}, optional
        Counter to use in the ChaCha state. Can be either
        a Python int in [0, 2**128) or a 2-element uint64 array.
        If not provided, the RNG is initialized at 0.
    key : {None, int, array_like}, optional
        Key to use in the ChaCha state.  Unlike seed, which is run through
        another RNG before use, the value in key is directly set. Can be either
        a Python int in [0, 2**256) or a 4-element uint64 array.
        key and seed cannot both be used.
    rounds : {None, int}, optional
        Number of rounds to run the ChaCha mixer. Must be an even integer.
          The standard number of rounds in 20.  Smaller values, usually 8 or
          more, can be used to reduce security properties of the random stream
          while improving performance.

    Attributes
    ----------
    lock: threading.Lock
        Lock instance that is shared so that the same bit git generator can
        be used in multiple Generators without corrupting the state. Code that
        generates values from a bit generator should hold the bit generator's
        lock.

    Notes
    -----
    ChaCha is a 64-bit PRNG that uses a counter-based design based on
    the ChaCha cipher [1]_. Instances using different values
    of the key produce independent sequences. ``ChaCha`` has a period
    of :math:`2^{128} - 1` and supports arbitrary advancing and
    jumping the sequence in increments of :math:`2^{64}`. These features allow
    multiple non-overlapping sequences to be generated.

    ``ChaCha`` provides a capsule containing function pointers that produce
    doubles, and unsigned 32 and 64- bit integers. These are not
    directly consumable in Python and must be consumed by a ``Generator``
    or similar object that supports low-level access.

    See ``AESCounter`` a related counter-based PRNG.

    **State and Seeding**

    The ``ChaCha`` state vector consists of a 16-element array of uint32
    that capture buffered draws from the distribution, an 8-element array of
    uint32s holding the seed, and an 2-element array of uint64 that holds the
    counter ([low, high]). The elements of the seed are the value provided by
    the user (or from the entropy pool). The final value rounds contains the
    number of rounds used. Typical values are  8, 12, or 20 (for high security).

    ``ChaCha`` is seeded using either a single 256-bit unsigned integer
    or a vector of 4 64-bit unsigned integers.  In either case, the seed is
    used as an input for a second random number generator,
    SplitMix64, and the output of this PRNG function is used as the initial
    state. Using a single 64-bit value for the seed can only initialize a small
    range of the possible initial state values.

    **Parallel Features**

    ``ChaCha`` can be used in parallel applications by calling the ``jump``
    method  to advances the state as-if :math:`2^{64}` random numbers have
    been generated. Alternatively, ``advance`` can be used to advance the
    counter for any positive step in [0, 2**128). When using ``jump``, all
    generators should be initialized with the same seed to ensure that the
    segments come from the same sequence.

    >>> from randomgen import Generator, ChaCha
    >>> rg = [Generator(ChaCha(1234)) for _ in range(10)]
    # Advance each ChaCha instances by i jumps
    >>> for i in range(10):
    ...     rg[i].bit_generator.jump(i)

    Alternatively, ``ChaCha`` can be used in parallel applications by using
    a sequence of distinct keys where each instance uses different key.

    >>> key = 2**93 + 2**65 + 2**33 + 2**17 + 2**9
    >>> rg = [Generator(ChaCha(key=key+i)) for i in range(10)]

    **Compatibility Guarantee**

    ``ChaCha`` makes a guarantee that a fixed seed and will always produce
    the same random integer stream.

    Examples
    --------
    >>> from randomgen import Generator, ChaCha
    >>> rg = Generator(ChaCha(1234, rounds=8))
    >>> rg.standard_normal()
    0.123  # random

    References
    ----------
    .. [1] Bernstein, D. J.. ChaCha, a variant of Salsa20.
         http://cr.yp.to/papers.html#chacha. 2008.01.28.
    """
    cdef chacha_state_t *rng_state
    cdef bitgen_t _bitgen
    cdef public object capsule
    cdef object _ctypes
    cdef object _cffi
    cdef public object lock

    def __init__(self, seed=None, counter=None, key=None, rounds=20):
        self.rng_state = <chacha_state_t *>PyArray_malloc_aligned(sizeof(chacha_state_t))
        if rounds % 2 != 0 or rounds <= 0:
            raise ValueError('rounds must be even and larger than 2')
        self.rng_state.rounds = rounds
        self.seed(seed, counter, key)

        self._bitgen.state = <void *>self.rng_state
        self._bitgen.next_uint64 = &chacha_uint64
        self._bitgen.next_uint32 = &chacha_uint32
        self._bitgen.next_double = &chacha_double
        self._bitgen.next_raw = &chacha_uint64

        self.lock = Lock()

        self._ctypes = None
        self._cffi = None

        cdef const char *name = "BitGenerator"
        self.capsule = PyCapsule_New(<void *>&self._bitgen, name, NULL)

    def __dealloc__(self):
        if self.rng_state:
            PyArray_free_aligned(self.rng_state)

    # Pickling support:
    def __getstate__(self):
        return self.state

    def __setstate__(self, state):
        self.state = state

    def __reduce__(self):
        from randomgen._pickle import __bit_generator_ctor
        return __bit_generator_ctor, (self.state['bit_generator'],), self.state

    def random_raw(self, size=None, output=True):
        """
        random_raw(self, size=None)

        Return randoms as generated by the underlying BitGenerator

        Parameters
        ----------
        size : int or tuple of ints, optional
            Output shape.  If the given shape is, e.g., ``(m, n, k)``, then
            ``m * n * k`` samples are drawn.  Default is None, in which case a
            single value is returned.
        output : bool, optional
            Output values.  Used for performance testing since the generated
            values are not returned.

        Returns
        -------
        out : uint or ndarray
            Drawn samples.

        Notes
        -----
        This method directly exposes the the raw underlying pseudo-random
        number generator. All values are returned as unsigned 64-bit
        values irrespective of the number of bits produced by the PRNG.

        See the class docstring for the number of bits returned.
        """
        return random_raw(&self._bitgen, self.lock, size, output)

    def _benchmark(self, Py_ssize_t cnt, method=u'uint64'):
        return benchmark(&self._bitgen, self.lock, cnt, method)

    def seed(self, seed=None, counter=None, key=None):
        """
        seed(seed=None, counter=None, key=None)

        Seed the generator.

        This method is called when ``ChaCha`` is initialized. It can be
        called again to re-seed the generator. For details, see
        ``ChaCha``.

        seed : {None, int}, optional
            Random seed initializing the pseudo-random number generator.
            Can be an integer in [0, 2**256-1], an array of 4 uint64 values
            or ``None`` (the default). If `seed` is ``None``, then  data is read
            from ``/dev/urandom`` (or the Windows analog) if available.  If
            unavailable, a hash of the time and process ID is used.
        counter : {None, int, array_like}, optional
            Counter to use in the ChaCha state. Can be either
            a Python int in [0, 2**128) or a 2-element uint64 array.
            If not provided, the RNG is initialized at 0.
        key : {None, int, array_like}, optional
            Key to use in the ChaCha state.  Unlike seed, which is run
            through another RNG before use, the value in key is directly set.
            Can be either a Python int in [0, 2**256) or a 2-element uint64
            array. key and seed cannot both be used.

        Raises
        ------
        ValueError
            If values are out of range for the PRNG.

        Notes
        -----
        The two representation of the counter and key are related through
        array[i] = (value // 2**(64*i)) % 2**64.
        """
        cdef int i

        if seed is not None and key is not None:
            raise ValueError('seed and key cannot be simultaneously used')

        if key is not None:
            seed = int_to_array(key, 'key', 256, 32)
        elif seed is not None:
            seed = seed_by_array(seed, 8)
        else:
            try:
                seed = random_entropy(8)
            except RuntimeError:
                seed = random_entropy(8)
        seed = seed.view(np.uint32)
        for i in range(8):
            self.rng_state.keysetup[i] = seed[i]

        if counter is not None:
            _counter = int_to_array(counter, 'counter', 128, 64)
            self.rng_state.ctr[0] = _counter[0]
            self.rng_state.ctr[1] = _counter[1]

    @property
    def state(self):
        """
        Get or set the PRNG state

        Returns
        -------
        state : dict
            Dictionary containing the information required to describe the
            state of the PRNG
        """
        cdef int i
        block = np.empty(16, dtype=np.uint32)
        keysetup = np.empty(8, dtype=np.uint32)
        ctr = np.empty(2, dtype=np.uint64)
        for i in range(16):
            block[i] = self.rng_state.block[i]
        for i in range(8):
            keysetup[i] = self.rng_state.keysetup[i]
        for i in range(2):
            ctr[i] = self.rng_state.ctr[i]

        return {'bit_generator': self.__class__.__name__,
                'state': {'block': block, 'keysetup':keysetup, 'ctr': ctr,
                          'rounds': self.rng_state.rounds}}

    @state.setter
    def state(self, value):
        if not isinstance(value, dict):
            raise TypeError('state must be a dict')
        bitgen = value.get('bit_generator', '')
        if bitgen != self.__class__.__name__:
            raise ValueError('state must be for a {0} '
                             'PRNG'.format(self.__class__.__name__))

        state = value['state']
        block = state['block']
        for i in range(16):
            self.rng_state.block[i] = block[i]
        keysetup = state['keysetup']
        for i in range(8):
            self.rng_state.keysetup[i] = keysetup[i]
        ctr = state['ctr']
        for i in range(2):
            self.rng_state.ctr[i] = ctr[i]
        self.rng_state.rounds = state['rounds']

    @property
    def ctypes(self):
        """
        ctypes interface

        Returns
        -------
        interface : namedtuple
            Named tuple containing ctypes wrapper

            * state_address - Memory address of the state struct
            * state - pointer to the state struct
            * next_uint64 - function pointer to produce 64 bit integers
            * next_uint32 - function pointer to produce 32 bit integers
            * next_double - function pointer to produce doubles
            * bitgen - pointer to the bit generator struct
        """
        if self._ctypes is None:
            self._ctypes = prepare_ctypes(&self._bitgen)

        return self._ctypes

    @property
    def cffi(self):
        """
        CFFI interface

        Returns
        -------
        interface : namedtuple
            Named tuple containing CFFI wrapper

            * state_address - Memory address of the state struct
            * state - pointer to the state struct
            * next_uint64 - function pointer to produce 64 bit integers
            * next_uint32 - function pointer to produce 32 bit integers
            * next_double - function pointer to produce doubles
            * bitgen - pointer to the bit generator struct
        """
        if self._cffi is not None:
            return self._cffi
        self._cffi = prepare_cffi(&self._bitgen)
        return self._cffi

    cdef jump_inplace(self, iter):
        """
        Jump state in-place

        Not part of public API

        Parameters
        ----------
        iter : integer, positive
            Number of times to jump the state of the rng.
        """
        self.advance(iter * int(2 ** 64))

    def jump(self, iter=1):
        """
        jump(iter=1)

        Jumps the state as-if 2**64 random numbers have been generated.

        Parameters
        ----------
        iter : integer, positive
            Number of times to jump the state of the rng.

        Returns
        -------
        self : ChaCha
            PRNG jumped iter times

        Notes
        -----
        Jumping the rng state resets any pre-computed random numbers. This is
        required to ensure exact reproducibility.
        """
        import warnings
        warnings.warn('jump (in-place) has been deprecated in favor of jumped'
                      ', which returns a new instance', DeprecationWarning)
        self.jump_inplace(iter)
        return self

    def jumped(self, iter=1):
        """
        jumped(iter=1)

        Returns a new bit generator with the state jumped

        The state of the returned big generator is jumped as-if
        2**(64 * iter) random numbers have been generated.

        Parameters
        ----------
        iter : integer, positive
            Number of times to jump the state of the bit generator returned

        Returns
        -------
        bit_generator : ChaCha
            New instance of generator jumped iter times
        """
        cdef ChaCha bit_generator

        bit_generator = self.__class__()
        bit_generator.state = self.state
        bit_generator.jump_inplace(iter)

        return bit_generator

    def advance(self, delta):
        """
        advance(delta)

        Advance the underlying RNG as-if delta draws have occurred.

        Parameters
        ----------
        delta : integer, positive
            Number of draws to advance the RNG.

        Returns
        -------
        self : ChaCha
            RNG advanced delta steps

        Notes
        -----
        Advancing a RNG updates the underlying RNG state as-if a given
        number of calls to the underlying RNG have been made. In general
        there is not a one-to-one relationship between the number output
        random values from a particular distribution and the number of
        draws from the core RNG.  This occurs for two reasons:

        * The random values are simulated using a rejection-based method
          and so, on average, more than one value from the underlying
          RNG is required to generate an single draw.
        * The number of bits required to generate a simulated value
          differs from the number of bits generated by the underlying
          RNG.  For example, two 16-bit integer values can be simulated
          from a single draw of a 32-bit RNG.

        Advancing the RNG state resets any pre-computed random numbers.
        This is required to ensure exact reproducibility.
        """
        cdef np.ndarray step

        delta = wrap_int(delta, 128)
        step = int_to_array(delta, 'delta', 128, 64)
        chacha_advance(self.rng_state, <uint64_t *>np.PyArray_DATA(step))
        return self
