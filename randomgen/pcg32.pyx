from cpython.pycapsule cimport PyCapsule_New, PyCapsule_GetPointer

try:
    from threading import Lock
except ImportError:
    from dummy_threading import Lock

import numpy as np
cimport numpy as np

from randomgen.common cimport *
from randomgen.distributions cimport bitgen_t
from randomgen.entropy import random_entropy

__all__ = ['PCG32']

np.import_array()

cdef extern from "src/pcg32/pcg32.h":

    cdef struct pcg_state_setseq_64:
        uint64_t state
        uint64_t inc

    ctypedef pcg_state_setseq_64 pcg32_random_t

    struct s_pcg32_state:
        pcg32_random_t *pcg_state

    ctypedef s_pcg32_state pcg32_state

    uint64_t pcg32_next64(pcg32_state *state)  nogil
    uint32_t pcg32_next32(pcg32_state *state)  nogil
    double pcg32_next_double(pcg32_state *state)  nogil
    void pcg32_jump(pcg32_state *state)
    void pcg32_advance_state(pcg32_state *state, uint64_t step)
    void pcg32_set_seed(pcg32_state *state, uint64_t seed, uint64_t inc)

cdef uint64_t pcg32_uint64(void* st) nogil:
    return pcg32_next64(<pcg32_state *>st)

cdef uint32_t pcg32_uint32(void *st) nogil:
    return pcg32_next32(<pcg32_state *> st)

cdef double pcg32_double(void* st) nogil:
    return pcg32_next_double(<pcg32_state *>st)

cdef uint64_t pcg32_raw(void* st) nogil:
    return <uint64_t>pcg32_next32(<pcg32_state *> st)


cdef class PCG32:
    u"""
    PCG32(seed=None, inc=0)

    Container for the PCG-32 pseudo-random number generator.

    Parameters
    ----------
    seed : {None, long}, optional
        Random seed initializing the pseudo-random number generator.
        Can be an integer in [0, 2**64] or ``None`` (the default).
        If `seed` is ``None``, then ``PCG32`` will try to read data
        from ``/dev/urandom`` (or the Windows analog) if available. If
        unavailable, a 64-bit hash of the time and process ID is used.
    inc : {None, int}, optional
        Stream to return.
        Can be an integer in [0, 2**64] or ``None`` (the default).  If `inc` is
        ``None``, then 0 is used.  Can be used with the same seed to
        produce multiple streams using other values of inc.

    Attributes
    ----------
    lock: threading.Lock
        Lock instance that is shared so that the same bit git generator can
        be used in multiple Generators without corrupting the state. Code that
        generates values from a bit generator should hold the bit generator's
        lock.

    Notes
    -----
    PCG-32 is a 64-bit implementation of O'Neill's permutation congruential
    generator ([1]_, [2]_). PCG-32 has a period of :math:`2^{64}` and supports
    advancing an arbitrary number of steps as well as :math:`2^{63}` streams.

    ``PCG32`` provides a capsule containing function pointers that produce
    doubles, and unsigned 32 and 64- bit integers. These are not
    directly consumable in Python and must be consumed by a ``Generator``
    or similar object that supports low-level access.

    Supports the method advance to advance the RNG an arbitrary number of
    steps. The state of the PCG-32 PRNG is represented by 2 64-bit unsigned
    integers.

    See ``PCG64`` for a similar implementation with a smaller period.

    **State and Seeding**

    The ``PCG32`` state vector consists of 2 unsigned 64-bit values.
    ``PCG32`` is seeded using a single 64-bit unsigned integer.
    In addition, a second 64-bit unsigned integer is used to set the stream.

    **Parallel Features**

    ``PCG32`` can be used in parallel applications in one of two ways.
    The preferable method is to use sub-streams, which are generated by using the
    same value of ``seed`` and incrementing the second value, ``inc``.

    >>> from randomgen import Generator, PCG32
    >>> rg = [Generator(PCG32(1234, i + 1)) for i in range(10)]

    The alternative method is to call ``advance`` with a different value on
    each instance to produce non-overlapping sequences.

    >>> rg = [Generator(PCG32(1234, i + 1)) for i in range(10)]
    >>> for i in range(10):
    ...     rg[i].bit_generator.advance(i * 2**32)

    **Compatibility Guarantee**

    ``PCG32`` makes a guarantee that a fixed seed and will always produce
    the same random integer stream.

    References
    ----------
    .. [1] "PCG, A Family of Better Random Number Generators",
           http://www.pcg-random.org/
    .. [2] O'Neill, Melissa E. "PCG: A Family of Simple Fast Space-Efficient
           Statistically Good Algorithms for Random Number Generation"
    """
    cdef pcg32_state rng_state
    cdef pcg32_random_t pcg32_random_state
    cdef bitgen_t _bitgen
    cdef public object capsule
    cdef object _ctypes
    cdef object _cffi
    cdef public object lock

    def __init__(self, seed=None, inc=0):
        self.rng_state.pcg_state = &self.pcg32_random_state
        self.seed(seed, inc)
        self.lock = Lock()

        self._bitgen.state = <void *>&self.rng_state
        self._bitgen.next_uint64 = &pcg32_uint64
        self._bitgen.next_uint32 = &pcg32_uint32
        self._bitgen.next_double = &pcg32_double
        self._bitgen.next_raw = &pcg32_raw

        self._ctypes = None
        self._cffi = None

        cdef const char *name = "BitGenerator"
        self.capsule = PyCapsule_New(<void *>&self._bitgen, name, NULL)

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

    def seed(self, seed=None, inc=0):
        """
        seed(seed=None, inc=0)

        Seed the generator.

        This method is called when ``PCG32`` is initialized. It can be
        called again to re-seed the generator. For details, see
        ``PCG32``.

        Parameters
        ----------
        seed : int, optional
            Seed for ``PCG64``. Integer between 0 and 2**64-1.
        inc : int, optional
            Increment to use for PCG stream. Integer between 0 and 2**64-1.

        Raises
        ------
        ValueError
            If seed values are out of range for the PRNG.
        """
        ub = 2 ** 64
        if seed is None:
            try:
                seed = <np.ndarray>random_entropy(2)
            except RuntimeError:
                seed = <np.ndarray>random_entropy(2, 'fallback')
            seed = seed.view(np.uint64).squeeze()
        else:
            err_msg = 'seed must be a scalar integer between 0 and ' \
                      '{ub}'.format(ub=ub)
            if not np.isscalar(seed):
                raise TypeError(err_msg)
            if int(seed) != seed:
                raise TypeError(err_msg)
            if seed < 0 or seed > ub:
                raise ValueError(err_msg)

        if not np.isscalar(inc):
            raise TypeError('inc must be a scalar integer between 0 '
                            'and {ub}'.format(ub=ub))
        if inc < 0 or inc > ub or int(inc) != inc:
            raise ValueError('inc must be a scalar integer between 0 '
                             'and {ub}'.format(ub=ub))

        pcg32_set_seed(&self.rng_state, <uint64_t>seed, <uint64_t>inc)

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
        return {'bit_generator': self.__class__.__name__,
                'state': {'state': self.rng_state.pcg_state.state,
                          'inc': self.rng_state.pcg_state.inc}}

    @state.setter
    def state(self, value):
        if not isinstance(value, dict):
            raise TypeError('state must be a dict')
        bitgen = value.get('bit_generator', '')
        if bitgen != self.__class__.__name__:
            raise ValueError('state must be for a {0} '
                             'PRNG'.format(self.__class__.__name__))
        self.rng_state.pcg_state.state = value['state']['state']
        self.rng_state.pcg_state.inc = value['state']['inc']

    def advance(self, delta):
        """
        advance(delta)

        Advance the underlying RNG as-if delta draws have occurred.

        Parameters
        ----------
        delta : integer, positive
            Number of draws to advance the RNG. Must be less than the
            size state variable in the underlying RNG.

        Returns
        -------
        self : PCG32
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
        """
        delta = wrap_int(delta, 64)
        pcg32_advance_state(&self.rng_state, <uint64_t>delta)
        return self

    cdef jump_inplace(self, iter):
        """
        Jump state in-place
        
        Not part of public API
        
        Parameters
        ----------
        iter : integer, positive
            Number of times to jump the state of the rng.
        
        Notes
        -----
        The step size is phi when divided by the period 2**64
        """
        step = int(0x9e3779b97f4a7c16)
        self.advance(iter * step)

    def jump(self, iter=1):
        """
        jump(iter=1)

        Jump the state a fixed increment

        Jumps the state as-if 11400714819323198486 random numbers have been
        generated.

        Parameters
        ----------
        iter : integer, positive
            Number of times to jump the state of the rng.

        Returns
        -------
        self : PCG32
            RNG jumped iter times

        Notes
        -----
        The step size is phi when divided by the period 2**64
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
        11400714819323198486 random numbers have been generated.

        Parameters
        ----------
        iter : integer, positive
            Number of times to jump the state of the bit generator returned

        Returns
        -------
        bit_generator : PCG32
            New instance of generator jumped iter times

        Notes
        -----
        The step size is phi when divided by the period 2**64            
        """
        cdef PCG32 bit_generator

        bit_generator = self.__class__()
        bit_generator.state = self.state
        bit_generator.jump_inplace(iter)

        return bit_generator

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

    @property
    def generator(self):
        """
        Removed, raises NotImplementedError
        """
        raise NotImplementedError('This method for accessing a Generator has'
                                  'been removed.')
