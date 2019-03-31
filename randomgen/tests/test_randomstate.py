import warnings

import pytest
import numpy as np
from numpy.testing import (
        assert_, assert_raises, assert_equal, assert_warns,
        assert_no_warnings, assert_array_equal, assert_array_almost_equal,
        suppress_warnings
        )
from numpy import random
import sys

import randomgen.mtrand


class TestSeed(object):
    def test_scalar(self):
        s = randomgen.mtrand.RandomState(0)
        assert_equal(s.randint(1000), 684)
        s = randomgen.mtrand.RandomState(4294967295)
        assert_equal(s.randint(1000), 419)

    def test_array(self):
        s = randomgen.mtrand.RandomState(range(10))
        assert_equal(s.randint(1000), 468)
        s = randomgen.mtrand.RandomState(np.arange(10))
        assert_equal(s.randint(1000), 468)
        s = randomgen.mtrand.RandomState([0])
        assert_equal(s.randint(1000), 973)
        s = randomgen.mtrand.RandomState([4294967295])
        assert_equal(s.randint(1000), 265)

    def test_invalid_scalar(self):
        # seed must be an unsigned 32 bit integer
        assert_raises(TypeError, randomgen.mtrand.RandomState, -0.5)
        assert_raises(ValueError, randomgen.mtrand.RandomState, -1)

    def test_invalid_array(self):
        # seed must be an unsigned 32 bit integer
        assert_raises(TypeError, randomgen.mtrand.RandomState, [-0.5])
        assert_raises(ValueError, randomgen.mtrand.RandomState, [-1])
        assert_raises(ValueError, randomgen.mtrand.RandomState, [4294967296])
        assert_raises(ValueError, randomgen.mtrand.RandomState, [1, 2, 4294967296])
        assert_raises(ValueError, randomgen.mtrand.RandomState, [1, -2, 4294967296])

    def test_invalid_array_shape(self):
        # gh-9832
        assert_raises(ValueError, randomgen.mtrand.RandomState, np.array([], dtype=np.int64))
        assert_raises(ValueError, randomgen.mtrand.RandomState, [[1, 2, 3]])
        assert_raises(ValueError, randomgen.mtrand.RandomState, [[1, 2, 3],
                                                          [4, 5, 6]])


class TestBinomial(object):
    def test_n_zero(self):
        # Tests the corner case of n == 0 for the binomial distribution.
        # binomial(0, p) should be zero for any p in [0, 1].
        # This test addresses issue #3480.
        zeros = np.zeros(2, dtype='int')
        for p in [0, .5, 1]:
            assert_(randomgen.mtrand.binomial(0, p) == 0)
            assert_array_equal(randomgen.mtrand.binomial(zeros, p), zeros)

    def test_p_is_nan(self):
        # Issue #4571.
        assert_raises(ValueError, randomgen.mtrand.binomial, 1, np.nan)


class TestMultinomial(object):
    def test_basic(self):
        randomgen.mtrand.multinomial(100, [0.2, 0.8])

    def test_zero_probability(self):
        randomgen.mtrand.multinomial(100, [0.2, 0.8, 0.0, 0.0, 0.0])

    def test_int_negative_interval(self):
        assert_(-5 <= randomgen.mtrand.randint(-5, -1) < -1)
        x = randomgen.mtrand.randint(-5, -1, 5)
        assert_(np.all(-5 <= x))
        assert_(np.all(x < -1))

    def test_size(self):
        # gh-3173
        p = [0.5, 0.5]
        assert_equal(randomgen.mtrand.multinomial(1, p, np.uint32(1)).shape, (1, 2))
        assert_equal(randomgen.mtrand.multinomial(1, p, np.uint32(1)).shape, (1, 2))
        assert_equal(randomgen.mtrand.multinomial(1, p, np.uint32(1)).shape, (1, 2))
        assert_equal(randomgen.mtrand.multinomial(1, p, [2, 2]).shape, (2, 2, 2))
        assert_equal(randomgen.mtrand.multinomial(1, p, (2, 2)).shape, (2, 2, 2))
        assert_equal(randomgen.mtrand.multinomial(1, p, np.array((2, 2))).shape,
                     (2, 2, 2))

        assert_raises(TypeError, randomgen.mtrand.multinomial, 1, p,
                      float(1))
        assert_raises(ValueError, randomgen.mtrand.multinomial, 1, [1.1, .1])


class TestSetState(object):
    def setup(self):
        self.seed = 1234567890
        self.prng = randomgen.mtrand.RandomState(self.seed)
        self.state = self.prng.get_state()

    def test_basic(self):
        old = self.prng.tomaxint(16)
        self.prng.set_state(self.state)
        new = self.prng.tomaxint(16)
        assert_(np.all(old == new))

    def test_gaussian_reset(self):
        # Make sure the cached every-other-Gaussian is reset.
        old = self.prng.standard_normal(size=3)
        self.prng.set_state(self.state)
        new = self.prng.standard_normal(size=3)
        assert_(np.all(old == new))

    def test_gaussian_reset_in_media_res(self):
        # When the state is saved with a cached Gaussian, make sure the
        # cached Gaussian is restored.

        self.prng.standard_normal()
        state = self.prng.get_state()
        old = self.prng.standard_normal(size=3)
        self.prng.set_state(state)
        new = self.prng.standard_normal(size=3)
        assert_(np.all(old == new))

    def test_backwards_compatibility(self):
        # Make sure we can accept old state tuples that do not have the
        # cached Gaussian value.
        old_state = self.state[:-2]
        x1 = self.prng.standard_normal(size=16)
        self.prng.set_state(old_state)
        x2 = self.prng.standard_normal(size=16)
        self.prng.set_state(self.state)
        x3 = self.prng.standard_normal(size=16)
        assert_(np.all(x1 == x2))
        assert_(np.all(x1 == x3))

    def test_negative_binomial(self):
        # Ensure that the negative binomial results take floating point
        # arguments without truncation.
        self.prng.negative_binomial(0.5, 0.5)


class TestRandint(object):

    rfunc = randomgen.mtrand.randint

    # valid integer/boolean types
    itype = [np.bool_, np.int8, np.uint8, np.int16, np.uint16,
             np.int32, np.uint32, np.int64, np.uint64]

    def test_unsupported_type(self):
        assert_raises(TypeError, self.rfunc, 1, dtype=float)

    def test_bounds_checking(self):
        for dt in self.itype:
            lbnd = 0 if dt is np.bool_ else np.iinfo(dt).min
            ubnd = 2 if dt is np.bool_ else np.iinfo(dt).max + 1
            assert_raises(ValueError, self.rfunc, lbnd - 1, ubnd, dtype=dt)
            assert_raises(ValueError, self.rfunc, lbnd, ubnd + 1, dtype=dt)
            assert_raises(ValueError, self.rfunc, ubnd, lbnd, dtype=dt)
            assert_raises(ValueError, self.rfunc, 1, 0, dtype=dt)

    def test_rng_zero_and_extremes(self):
        for dt in self.itype:
            lbnd = 0 if dt is np.bool_ else np.iinfo(dt).min
            ubnd = 2 if dt is np.bool_ else np.iinfo(dt).max + 1

            tgt = ubnd - 1
            assert_equal(self.rfunc(tgt, tgt + 1, size=1000, dtype=dt), tgt)

            tgt = lbnd
            assert_equal(self.rfunc(tgt, tgt + 1, size=1000, dtype=dt), tgt)

            tgt = (lbnd + ubnd)//2
            assert_equal(self.rfunc(tgt, tgt + 1, size=1000, dtype=dt), tgt)

    def test_full_range(self):
        # Test for ticket #1690

        for dt in self.itype:
            lbnd = 0 if dt is np.bool_ else np.iinfo(dt).min
            ubnd = 2 if dt is np.bool_ else np.iinfo(dt).max + 1

            try:
                self.rfunc(lbnd, ubnd, dtype=dt)
            except Exception as e:
                raise AssertionError("No error should have been raised, "
                                     "but one was with the following "
                                     "message:\n\n%s" % str(e))

    def test_in_bounds_fuzz(self):
        # Don't use fixed seed
        randomgen.mtrand.seed()

        for dt in self.itype[1:]:
            for ubnd in [4, 8, 16]:
                vals = self.rfunc(2, ubnd, size=2**16, dtype=dt)
                assert_(vals.max() < ubnd)
                assert_(vals.min() >= 2)

        vals = self.rfunc(0, 2, size=2**16, dtype=np.bool_)

        assert_(vals.max() < 2)
        assert_(vals.min() >= 0)

    def test_repeatability(self):
        import hashlib
        # We use a md5 hash of generated sequences of 1000 samples
        # in the range [0, 6) for all but bool, where the range
        # is [0, 2). Hashes are for little endian numbers.
        tgt = {'bool': '7dd3170d7aa461d201a65f8bcf3944b0',
               'int16': '1b7741b80964bb190c50d541dca1cac1',
               'int32': '4dc9fcc2b395577ebb51793e58ed1a05',
               'int64': '17db902806f448331b5a758d7d2ee672',
               'int8': '27dd30c4e08a797063dffac2490b0be6',
               'uint16': '1b7741b80964bb190c50d541dca1cac1',
               'uint32': '4dc9fcc2b395577ebb51793e58ed1a05',
               'uint64': '17db902806f448331b5a758d7d2ee672',
               'uint8': '27dd30c4e08a797063dffac2490b0be6'}

        for dt in self.itype[1:]:
            randomgen.mtrand.seed(1234)

            # view as little endian for hash
            if sys.byteorder == 'little':
                val = self.rfunc(0, 6, size=1000, dtype=dt)
            else:
                val = self.rfunc(0, 6, size=1000, dtype=dt).byteswap()

            res = hashlib.md5(val.view(np.int8)).hexdigest()
            assert_(tgt[np.dtype(dt).name] == res)

        # bools do not depend on endianness
        randomgen.mtrand.seed(1234)
        val = self.rfunc(0, 2, size=1000, dtype=bool).view(np.int8)
        res = hashlib.md5(val).hexdigest()
        assert_(tgt[np.dtype(bool).name] == res)

    def test_int64_uint64_corner_case(self):
        # When stored in Numpy arrays, `lbnd` is casted
        # as np.int64, and `ubnd` is casted as np.uint64.
        # Checking whether `lbnd` >= `ubnd` used to be
        # done solely via direct comparison, which is incorrect
        # because when Numpy tries to compare both numbers,
        # it casts both to np.float64 because there is
        # no integer superset of np.int64 and np.uint64. However,
        # `ubnd` is too large to be represented in np.float64,
        # causing it be round down to np.iinfo(np.int64).max,
        # leading to a ValueError because `lbnd` now equals
        # the new `ubnd`.

        dt = np.int64
        tgt = np.iinfo(np.int64).max
        lbnd = np.int64(np.iinfo(np.int64).max)
        ubnd = np.uint64(np.iinfo(np.int64).max + 1)

        # None of these function calls should
        # generate a ValueError now.
        actual = randomgen.mtrand.randint(lbnd, ubnd, dtype=dt)
        assert_equal(actual, tgt)

    def test_respect_dtype_singleton(self):
        # See gh-7203
        for dt in self.itype:
            lbnd = 0 if dt is np.bool_ else np.iinfo(dt).min
            ubnd = 2 if dt is np.bool_ else np.iinfo(dt).max + 1

            sample = self.rfunc(lbnd, ubnd, dtype=dt)
            assert_equal(sample.dtype, np.dtype(dt))

        for dt in (bool, int, np.long):
            lbnd = 0 if dt is bool else np.iinfo(dt).min
            ubnd = 2 if dt is bool else np.iinfo(dt).max + 1

            # gh-7284: Ensure that we get Python data types
            sample = self.rfunc(lbnd, ubnd, dtype=dt)
            assert_(not hasattr(sample, 'dtype'))
            assert_equal(type(sample), dt)


class TestRandomDist(object):
    # Make sure the random distribution returns the correct value for a
    # given seed

    def setup(self):
        self.seed = 1234567890

    def test_rand(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.rand(3, 2)
        desired = np.array([[0.61879477158567997, 0.59162362775974664],
                            [0.88868358904449662, 0.89165480011560816],
                            [0.4575674820298663, 0.7781880808593471]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_randn(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.randn(3, 2)
        desired = np.array([[1.34016345771863121, 1.73759122771936081],
                           [1.498988344300628, -0.2286433324536169],
                           [2.031033998682787, 2.17032494605655257]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_randint(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.randint(-99, 99, size=(3, 2))
        desired = np.array([[31, 3],
                            [-52, 41],
                            [-48, -66]])
        assert_array_equal(actual, desired)

    def test_random_integers(self):
        randomgen.mtrand.seed(self.seed)
        with suppress_warnings() as sup:
            w = sup.record(DeprecationWarning)
            actual = randomgen.mtrand.random_integers(-99, 99, size=(3, 2))
            assert_(len(w) == 1)
        desired = np.array([[31, 3],
                            [-52, 41],
                            [-48, -66]])
        assert_array_equal(actual, desired)

        randomgen.mtrand.seed(self.seed)
        with suppress_warnings() as sup:
            w = sup.record(DeprecationWarning)
            actual = randomgen.mtrand.random_integers(198, size=(3, 2))
            assert_(len(w) == 1)
        assert_array_equal(actual, desired + 100)


    def test_tomaxint(self):
        randomgen.mtrand.seed(self.seed)
        rs = randomgen.mtrand.RandomState(self.seed)
        actual = rs.tomaxint(size=(3, 2))
        if np.iinfo(np.int).max == 2147483647:
            desired = np.array([[1328851649,  731237375],
                                [1270502067,  320041495],
                                [1908433478,  499156889]], dtype=np.int64)
        else:
            desired = np.array([[2191376711989041151, 1690157618316108847],
                                [7169946713346608947, 7224755809774414763],
                                [8440630163640693052, 5131664369514206857]],
                               dtype=np.int64)
        assert_equal(actual, desired)

    def test_random_integers_max_int(self):
        # Tests whether random_integers can generate the
        # maximum allowed Python int that can be converted
        # into a C long. Previous implementations of this
        # method have thrown an OverflowError when attempting
        # to generate this integer.
        with suppress_warnings() as sup:
            w = sup.record(DeprecationWarning)
            actual = randomgen.mtrand.random_integers(np.iinfo('l').max,
                                               np.iinfo('l').max)
            assert_(len(w) == 1)

        desired = np.iinfo('l').max
        assert_equal(actual, desired)

    def test_random_integers_deprecated(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)

            # DeprecationWarning raised with high == None
            assert_raises(DeprecationWarning,
                          randomgen.mtrand.random_integers,
                          np.iinfo('l').max)

            # DeprecationWarning raised with high != None
            assert_raises(DeprecationWarning,
                          randomgen.mtrand.random_integers,
                          np.iinfo('l').max, np.iinfo('l').max)

    def test_random_sample(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.random_sample((3, 2))
        desired = np.array([[0.61879477158567997, 0.59162362775974664],
                            [0.88868358904449662, 0.89165480011560816],
                            [0.4575674820298663, 0.7781880808593471]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_rand_singleton(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.rand()
        desired = np.array(0.61879477158567997)
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_choice_uniform_replace(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.choice(4, 4)
        desired = np.array([2, 3, 2, 3])
        assert_array_equal(actual, desired)

    def test_choice_nonuniform_replace(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.choice(4, 4, p=[0.4, 0.4, 0.1, 0.1])
        desired = np.array([1, 1, 2, 2])
        assert_array_equal(actual, desired)

    def test_choice_uniform_noreplace(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.choice(4, 3, replace=False)
        desired = np.array([0, 1, 3])
        assert_array_equal(actual, desired)

    def test_choice_nonuniform_noreplace(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.choice(4, 3, replace=False,
                                  p=[0.1, 0.3, 0.5, 0.1])
        desired = np.array([2, 3, 1])
        assert_array_equal(actual, desired)

    def test_choice_noninteger(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.choice(['a', 'b', 'c', 'd'], 4)
        desired = np.array(['c', 'd', 'c', 'd'])
        assert_array_equal(actual, desired)

    def test_choice_exceptions(self):
        sample = randomgen.mtrand.choice
        assert_raises(ValueError, sample, -1, 3)
        assert_raises(ValueError, sample, 3., 3)
        assert_raises(ValueError, sample, [[1, 2], [3, 4]], 3)
        assert_raises(ValueError, sample, [], 3)
        assert_raises(ValueError, sample, [1, 2, 3, 4], 3,
                      p=[[0.25, 0.25], [0.25, 0.25]])
        assert_raises(ValueError, sample, [1, 2], 3, p=[0.4, 0.4, 0.2])
        assert_raises(ValueError, sample, [1, 2], 3, p=[1.1, -0.1])
        assert_raises(ValueError, sample, [1, 2], 3, p=[0.4, 0.4])
        assert_raises(ValueError, sample, [1, 2, 3], 4, replace=False)
        # gh-13087
        assert_raises(ValueError, sample, [1, 2, 3], -2, replace=False)
        assert_raises(ValueError, sample, [1, 2, 3], (-1,), replace=False)
        assert_raises(ValueError, sample, [1, 2, 3], (-1, 1), replace=False)
        assert_raises(ValueError, sample, [1, 2, 3], 2,
                      replace=False, p=[1, 0, 0])

    def test_choice_return_shape(self):
        p = [0.1, 0.9]
        # Check scalar
        assert_(np.isscalar(randomgen.mtrand.choice(2, replace=True)))
        assert_(np.isscalar(randomgen.mtrand.choice(2, replace=False)))
        assert_(np.isscalar(randomgen.mtrand.choice(2, replace=True, p=p)))
        assert_(np.isscalar(randomgen.mtrand.choice(2, replace=False, p=p)))
        assert_(np.isscalar(randomgen.mtrand.choice([1, 2], replace=True)))
        assert_(randomgen.mtrand.choice([None], replace=True) is None)
        a = np.array([1, 2])
        arr = np.empty(1, dtype=object)
        arr[0] = a
        assert_(randomgen.mtrand.choice(arr, replace=True) is a)

        # Check 0-d array
        s = tuple()
        assert_(not np.isscalar(randomgen.mtrand.choice(2, s, replace=True)))
        assert_(not np.isscalar(randomgen.mtrand.choice(2, s, replace=False)))
        assert_(not np.isscalar(randomgen.mtrand.choice(2, s, replace=True, p=p)))
        assert_(not np.isscalar(randomgen.mtrand.choice(2, s, replace=False, p=p)))
        assert_(not np.isscalar(randomgen.mtrand.choice([1, 2], s, replace=True)))
        assert_(randomgen.mtrand.choice([None], s, replace=True).ndim == 0)
        a = np.array([1, 2])
        arr = np.empty(1, dtype=object)
        arr[0] = a
        assert_(randomgen.mtrand.choice(arr, s, replace=True).item() is a)

        # Check multi dimensional array
        s = (2, 3)
        p = [0.1, 0.1, 0.1, 0.1, 0.4, 0.2]
        assert_equal(randomgen.mtrand.choice(6, s, replace=True).shape, s)
        assert_equal(randomgen.mtrand.choice(6, s, replace=False).shape, s)
        assert_equal(randomgen.mtrand.choice(6, s, replace=True, p=p).shape, s)
        assert_equal(randomgen.mtrand.choice(6, s, replace=False, p=p).shape, s)
        assert_equal(randomgen.mtrand.choice(np.arange(6), s, replace=True).shape, s)

        # Check zero-size
        assert_equal(randomgen.mtrand.randint(0, 0, size=(3, 0, 4)).shape, (3, 0, 4))
        assert_equal(randomgen.mtrand.randint(0, -10, size=0).shape, (0,))
        assert_equal(randomgen.mtrand.randint(10, 10, size=0).shape, (0,))
        assert_equal(randomgen.mtrand.choice(0, size=0).shape, (0,))
        assert_equal(randomgen.mtrand.choice([], size=(0,)).shape, (0,))
        assert_equal(randomgen.mtrand.choice(['a', 'b'], size=(3, 0, 4)).shape, (3, 0, 4))
        assert_raises(ValueError, randomgen.mtrand.choice, [], 10)

    def test_choice_nan_probabilities(self):
        a = np.array([42, 1, 2])
        p = [None, None, None]
        assert_raises(ValueError, randomgen.mtrand.choice, a, p=p)

    def test_bytes(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.bytes(10)
        desired = b'\x82Ui\x9e\xff\x97+Wf\xa5'
        assert_equal(actual, desired)

    def test_shuffle(self):
        # Test lists, arrays (of various dtypes), and multidimensional versions
        # of both, c-contiguous or not:
        for conv in [lambda x: np.array([]),
                     lambda x: x,
                     lambda x: np.asarray(x).astype(np.int8),
                     lambda x: np.asarray(x).astype(np.float32),
                     lambda x: np.asarray(x).astype(np.complex64),
                     lambda x: np.asarray(x).astype(object),
                     lambda x: [(i, i) for i in x],
                     lambda x: np.asarray([[i, i] for i in x]),
                     lambda x: np.vstack([x, x]).T,
                     # gh-11442
                     lambda x: (np.asarray([(i, i) for i in x],
                                           [("a", int), ("b", int)])
                                .view(np.recarray)),
                     # gh-4270
                     lambda x: np.asarray([(i, i) for i in x],
                                          [("a", object, 1),
                                           ("b", np.int32, 1)])]:
            randomgen.mtrand.seed(self.seed)
            alist = conv([1, 2, 3, 4, 5, 6, 7, 8, 9, 0])
            randomgen.mtrand.shuffle(alist)
            actual = alist
            desired = conv([0, 1, 9, 6, 2, 4, 5, 8, 7, 3])
            assert_array_equal(actual, desired)

    def test_permutation(self):
        randomgen.mtrand.seed(self.seed)
        alist = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]
        actual = randomgen.mtrand.permutation(alist)
        desired = [0, 1, 9, 6, 2, 4, 5, 8, 7, 3]
        assert_array_equal(actual, desired)

        randomgen.mtrand.seed(self.seed)
        arr_2d = np.atleast_2d([1, 2, 3, 4, 5, 6, 7, 8, 9, 0]).T
        actual = randomgen.mtrand.permutation(arr_2d)
        assert_array_equal(actual, np.atleast_2d(desired).T)

    def test_shuffle_masked(self):
        # gh-3263
        a = np.ma.masked_values(np.reshape(range(20), (5, 4)) % 3 - 1, -1)
        b = np.ma.masked_values(np.arange(20) % 3 - 1, -1)
        a_orig = a.copy()
        b_orig = b.copy()
        for i in range(50):
            randomgen.mtrand.shuffle(a)
            assert_equal(
                sorted(a.data[~a.mask]), sorted(a_orig.data[~a_orig.mask]))
            randomgen.mtrand.shuffle(b)
            assert_equal(
                sorted(b.data[~b.mask]), sorted(b_orig.data[~b_orig.mask]))

    def test_beta(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.beta(.1, .9, size=(3, 2))
        desired = np.array(
                [[1.45341850513746058e-02, 5.31297615662868145e-04],
                 [1.85366619058432324e-06, 4.19214516800110563e-03],
                 [1.58405155108498093e-04, 1.26252891949397652e-04]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_binomial(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.binomial(100.123, .456, size=(3, 2))
        desired = np.array([[37, 43],
                            [42, 48],
                            [46, 45]])
        assert_array_equal(actual, desired)

        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.binomial(100.123, .456)
        desired = 37
        assert_array_equal(actual, desired)

    def test_chisquare(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.chisquare(50, size=(3, 2))
        desired = np.array([[63.87858175501090585, 68.68407748911370447],
                            [65.77116116901505904, 47.09686762438974483],
                            [72.3828403199695174, 74.18408615260374006]])
        assert_array_almost_equal(actual, desired, decimal=13)

    def test_dirichlet(self):
        randomgen.mtrand.seed(self.seed)
        alpha = np.array([51.72840233779265162, 39.74494232180943953])
        actual = randomgen.mtrand.dirichlet(alpha, size=(3, 2))
        desired = np.array([[[0.54539444573611562, 0.45460555426388438],
                             [0.62345816822039413, 0.37654183177960598]],
                            [[0.55206000085785778, 0.44793999914214233],
                             [0.58964023305154301, 0.41035976694845688]],
                            [[0.59266909280647828, 0.40733090719352177],
                             [0.56974431743975207, 0.43025568256024799]]])
        assert_array_almost_equal(actual, desired, decimal=15)

        randomgen.mtrand.seed(self.seed)
        alpha = np.array([51.72840233779265162, 39.74494232180943953])
        actual = randomgen.mtrand.dirichlet(alpha)
        assert_array_almost_equal(actual, desired[0, 0], decimal=15)


    def test_dirichlet_size(self):
        # gh-3173
        p = np.array([51.72840233779265162, 39.74494232180943953])
        assert_equal(randomgen.mtrand.dirichlet(p, np.uint32(1)).shape, (1, 2))
        assert_equal(randomgen.mtrand.dirichlet(p, np.uint32(1)).shape, (1, 2))
        assert_equal(randomgen.mtrand.dirichlet(p, np.uint32(1)).shape, (1, 2))
        assert_equal(randomgen.mtrand.dirichlet(p, [2, 2]).shape, (2, 2, 2))
        assert_equal(randomgen.mtrand.dirichlet(p, (2, 2)).shape, (2, 2, 2))
        assert_equal(randomgen.mtrand.dirichlet(p, np.array((2, 2))).shape, (2, 2, 2))

        assert_raises(TypeError, randomgen.mtrand.dirichlet, p, float(1))

    def test_dirichlet_bad_alpha(self):
        # gh-2089
        alpha = np.array([5.4e-01, -1.0e-16])
        assert_raises(ValueError, randomgen.mtrand.dirichlet, alpha)

    def test_exponential(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.exponential(1.1234, size=(3, 2))
        desired = np.array([[1.08342649775011624, 1.00607889924557314],
                            [2.46628830085216721, 2.49668106809923884],
                            [0.68717433461363442, 1.69175666993575979]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_exponential_0(self):
        assert_equal(randomgen.mtrand.exponential(scale=0), 0)
        assert_raises(ValueError, randomgen.mtrand.exponential, scale=-0.)

    def test_f(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.f(12, 77, size=(3, 2))
        desired = np.array([[1.21975394418575878, 1.75135759791559775],
                            [1.44803115017146489, 1.22108959480396262],
                            [1.02176975757740629, 1.34431827623300415]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_gamma(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.gamma(5, 3, size=(3, 2))
        desired = np.array([[24.60509188649287182, 28.54993563207210627],
                            [26.13476110204064184, 12.56988482927716078],
                            [31.71863275789960568, 33.30143302795922011]])
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_gamma_0(self):
        assert_equal(randomgen.mtrand.gamma(shape=0, scale=0), 0)
        assert_raises(ValueError, randomgen.mtrand.gamma, shape=-0., scale=-0.)

    def test_geometric(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.geometric(.123456789, size=(3, 2))
        desired = np.array([[8, 7],
                            [17, 17],
                            [5, 12]])
        assert_array_equal(actual, desired)

    def test_gumbel(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.gumbel(loc=.123456789, scale=2.0, size=(3, 2))
        desired = np.array([[0.19591898743416816, 0.34405539668096674],
                            [-1.4492522252274278, -1.47374816298446865],
                            [1.10651090478803416, -0.69535848626236174]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_gumbel_0(self):
        assert_equal(randomgen.mtrand.gumbel(scale=0), 0)
        assert_raises(ValueError, randomgen.mtrand.gumbel, scale=-0.)

    def test_hypergeometric(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.hypergeometric(10.1, 5.5, 14, size=(3, 2))
        desired = np.array([[10, 10],
                            [10, 10],
                            [9, 9]])
        assert_array_equal(actual, desired)

        # Test nbad = 0
        actual = randomgen.mtrand.hypergeometric(5, 0, 3, size=4)
        desired = np.array([3, 3, 3, 3])
        assert_array_equal(actual, desired)

        actual = randomgen.mtrand.hypergeometric(15, 0, 12, size=4)
        desired = np.array([12, 12, 12, 12])
        assert_array_equal(actual, desired)

        # Test ngood = 0
        actual = randomgen.mtrand.hypergeometric(0, 5, 3, size=4)
        desired = np.array([0, 0, 0, 0])
        assert_array_equal(actual, desired)

        actual = randomgen.mtrand.hypergeometric(0, 15, 12, size=4)
        desired = np.array([0, 0, 0, 0])
        assert_array_equal(actual, desired)

    def test_laplace(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.laplace(loc=.123456789, scale=2.0, size=(3, 2))
        desired = np.array([[0.66599721112760157, 0.52829452552221945],
                            [3.12791959514407125, 3.18202813572992005],
                            [-0.05391065675859356, 1.74901336242837324]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_laplace_0(self):
        assert_equal(randomgen.mtrand.laplace(scale=0), 0)
        assert_raises(ValueError, randomgen.mtrand.laplace, scale=-0.)

    def test_logistic(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.logistic(loc=.123456789, scale=2.0, size=(3, 2))
        desired = np.array([[1.09232835305011444, 0.8648196662399954],
                            [4.27818590694950185, 4.33897006346929714],
                            [-0.21682183359214885, 2.63373365386060332]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_lognormal(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.lognormal(mean=.123456789, sigma=2.0, size=(3, 2))
        desired = np.array([[16.50698631688883822, 36.54846706092654784],
                            [22.67886599981281748, 0.71617561058995771],
                            [65.72798501792723869, 86.84341601437161273]])
        assert_array_almost_equal(actual, desired, decimal=13)

    def test_lognormal_0(self):
        assert_equal(randomgen.mtrand.lognormal(sigma=0), 1)
        assert_raises(ValueError, randomgen.mtrand.lognormal, sigma=-0.)

    def test_logseries(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.logseries(p=.923456789, size=(3, 2))
        desired = np.array([[2, 2],
                            [6, 17],
                            [3, 6]])
        assert_array_equal(actual, desired)

    def test_multinomial(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.multinomial(20, [1/6.]*6, size=(3, 2))
        desired = np.array([[[4, 3, 5, 4, 2, 2],
                             [5, 2, 8, 2, 2, 1]],
                            [[3, 4, 3, 6, 0, 4],
                             [2, 1, 4, 3, 6, 4]],
                            [[4, 4, 2, 5, 2, 3],
                             [4, 3, 4, 2, 3, 4]]])
        assert_array_equal(actual, desired)

    def test_multivariate_normal(self):
        randomgen.mtrand.seed(self.seed)
        mean = (.123456789, 10)
        cov = [[1, 0], [0, 1]]
        size = (3, 2)
        actual = randomgen.mtrand.multivariate_normal(mean, cov, size)
        desired = np.array([[[1.463620246718631, 11.73759122771936 ],
                             [1.622445133300628, 9.771356667546383]],
                            [[2.154490787682787, 12.170324946056553],
                             [1.719909438201865, 9.230548443648306]],
                            [[0.689515026297799, 9.880729819607714],
                             [-0.023054015651998, 9.201096623542879]]])

        assert_array_almost_equal(actual, desired, decimal=15)

        # Check for default size, was raising deprecation warning
        actual = randomgen.mtrand.multivariate_normal(mean, cov)
        desired = np.array([0.895289569463708, 9.17180864067987])
        assert_array_almost_equal(actual, desired, decimal=15)

        # Check that non positive-semidefinite covariance warns with
        # RuntimeWarning
        mean = [0, 0]
        cov = [[1, 2], [2, 1]]
        assert_warns(RuntimeWarning, randomgen.mtrand.multivariate_normal, mean, cov)

        # and that it doesn't warn with RuntimeWarning check_valid='ignore'
        assert_no_warnings(randomgen.mtrand.multivariate_normal, mean, cov,
                           check_valid='ignore')

        # and that it raises with RuntimeWarning check_valid='raises'
        assert_raises(ValueError, randomgen.mtrand.multivariate_normal, mean, cov,
                      check_valid='raise')

        cov = np.array([[1, 0.1], [0.1, 1]], dtype=np.float32)
        with suppress_warnings() as sup:
            randomgen.mtrand.multivariate_normal(mean, cov)
            w = sup.record(RuntimeWarning)
            assert len(w) == 0

        mu = np.zeros(2)
        cov = np.eye(2)
        assert_raises(ValueError, randomgen.mtrand.multivariate_normal, mean,
                      cov, check_valid='other')
        assert_raises(ValueError, randomgen.mtrand.multivariate_normal,
                      np.zeros((2, 1, 1)), cov)
        assert_raises(ValueError, randomgen.mtrand.multivariate_normal,
                      mu, np.empty((3, 2)))
        assert_raises(ValueError, randomgen.mtrand.multivariate_normal,
                      mu, np.eye(3))

    def test_negative_binomial(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.negative_binomial(n=100, p=.12345, size=(3, 2))
        desired = np.array([[848, 841],
                            [892, 611],
                            [779, 647]])
        assert_array_equal(actual, desired)

    def test_noncentral_chisquare(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.noncentral_chisquare(df=5, nonc=5, size=(3, 2))
        desired = np.array([[23.91905354498517511, 13.35324692733826346],
                            [31.22452661329736401, 16.60047399466177254],
                            [5.03461598262724586, 17.94973089023519464]])
        assert_array_almost_equal(actual, desired, decimal=14)

        actual = randomgen.mtrand.noncentral_chisquare(df=.5, nonc=.2, size=(3, 2))
        desired = np.array([[1.47145377828516666,  0.15052899268012659],
                            [0.00943803056963588,  1.02647251615666169],
                            [0.332334982684171,  0.15451287602753125]])
        assert_array_almost_equal(actual, desired, decimal=14)

        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.noncentral_chisquare(df=5, nonc=0, size=(3, 2))
        desired = np.array([[9.597154162763948, 11.725484450296079],
                            [10.413711048138335, 3.694475922923986],
                            [13.484222138963087, 14.377255424602957]])
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_noncentral_f(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.noncentral_f(dfnum=5, dfden=2, nonc=1,
                                        size=(3, 2))
        desired = np.array([[1.40598099674926669, 0.34207973179285761],
                            [3.57715069265772545, 7.92632662577829805],
                            [0.43741599463544162, 1.1774208752428319]])
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_normal(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.normal(loc=.123456789, scale=2.0, size=(3, 2))
        desired = np.array([[2.80378370443726244, 3.59863924443872163],
                            [3.121433477601256, -0.33382987590723379],
                            [4.18552478636557357, 4.46410668111310471]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_normal_0(self):
        assert_equal(randomgen.mtrand.normal(scale=0), 0)
        assert_raises(ValueError, randomgen.mtrand.normal, scale=-0.)

    def test_pareto(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.pareto(a=.123456789, size=(3, 2))
        desired = np.array(
                [[2.46852460439034849e+03, 1.41286880810518346e+03],
                 [5.28287797029485181e+07, 6.57720981047328785e+07],
                 [1.40840323350391515e+02, 1.98390255135251704e+05]])
        # For some reason on 32-bit x86 Ubuntu 12.10 the [1, 0] entry in this
        # matrix differs by 24 nulps. Discussion:
        #   https://mail.python.org/pipermail/numpy-discussion/2012-September/063801.html
        # Consensus is that this is probably some gcc quirk that affects
        # rounding but not in any important way, so we just use a looser
        # tolerance on this test:
        np.testing.assert_array_almost_equal_nulp(actual, desired, nulp=30)

    def test_poisson(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.poisson(lam=.123456789, size=(3, 2))
        desired = np.array([[0, 0],
                            [1, 0],
                            [0, 0]])
        assert_array_equal(actual, desired)

    def test_poisson_exceptions(self):
        lambig = np.iinfo('l').max
        lamneg = -1
        assert_raises(ValueError, randomgen.mtrand.poisson, lamneg)
        assert_raises(ValueError, randomgen.mtrand.poisson, [lamneg]*10)
        assert_raises(ValueError, randomgen.mtrand.poisson, lambig)
        assert_raises(ValueError, randomgen.mtrand.poisson, [lambig]*10)

    def test_power(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.power(a=.123456789, size=(3, 2))
        desired = np.array([[0.02048932883240791, 0.01424192241128213],
                            [0.38446073748535298, 0.39499689943484395],
                            [0.00177699707563439, 0.13115505880863756]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_rayleigh(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.rayleigh(scale=10, size=(3, 2))
        desired = np.array([[13.8882496494248393, 13.383318339044731],
                            [20.95413364294492098, 21.08285015800712614],
                            [11.06066537006854311, 17.35468505778271009]])
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_rayleigh_0(self):
        assert_equal(randomgen.mtrand.rayleigh(scale=0), 0)
        assert_raises(ValueError, randomgen.mtrand.rayleigh, scale=-0.)

    def test_standard_cauchy(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.standard_cauchy(size=(3, 2))
        desired = np.array([[0.77127660196445336, -6.55601161955910605],
                            [0.93582023391158309, -2.07479293013759447],
                            [-4.74601644297011926, 0.18338989290760804]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_standard_exponential(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.standard_exponential(size=(3, 2))
        desired = np.array([[0.96441739162374596, 0.89556604882105506],
                            [2.1953785836319808, 2.22243285392490542],
                            [0.6116915921431676, 1.50592546727413201]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_standard_gamma(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.standard_gamma(shape=3, size=(3, 2))
        desired = np.array([[5.50841531318455058, 6.62953470301903103],
                            [5.93988484943779227, 2.31044849402133989],
                            [7.54838614231317084, 8.012756093271868]])
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_standard_gamma_0(self):
        assert_equal(randomgen.mtrand.standard_gamma(shape=0), 0)
        assert_raises(ValueError, randomgen.mtrand.standard_gamma, shape=-0.)

    def test_standard_normal(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.standard_normal(size=(3, 2))
        desired = np.array([[1.34016345771863121, 1.73759122771936081],
                            [1.498988344300628, -0.2286433324536169],
                            [2.031033998682787, 2.17032494605655257]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_randn_singleton(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.randn()
        desired = np.array(1.34016345771863121)
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_standard_t(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.standard_t(df=10, size=(3, 2))
        desired = np.array([[0.97140611862659965, -0.08830486548450577],
                            [1.36311143689505321, -0.55317463909867071],
                            [-0.18473749069684214, 0.61181537341755321]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_triangular(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.triangular(left=5.12, mode=10.23, right=20.34,
                                      size=(3, 2))
        desired = np.array([[12.68117178949215784, 12.4129206149193152],
                            [16.20131377335158263, 16.25692138747600524],
                            [11.20400690911820263, 14.4978144835829923]])
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_uniform(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.uniform(low=1.23, high=10.54, size=(3, 2))
        desired = np.array([[6.99097932346268003, 6.73801597444323974],
                            [9.50364421400426274, 9.53130618907631089],
                            [5.48995325769805476, 8.47493103280052118]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_uniform_range_bounds(self):
        fmin = np.finfo('float').min
        fmax = np.finfo('float').max

        func = randomgen.mtrand.uniform
        assert_raises(OverflowError, func, -np.inf, 0)
        assert_raises(OverflowError, func,  0,      np.inf)
        assert_raises(OverflowError, func,  fmin,   fmax)
        assert_raises(OverflowError, func, [-np.inf], [0])
        assert_raises(OverflowError, func, [0], [np.inf])

        # (fmax / 1e17) - fmin is within range, so this should not throw
        # account for i386 extended precision DBL_MAX / 1e17 + DBL_MAX >
        # DBL_MAX by increasing fmin a bit
        randomgen.mtrand.uniform(low=np.nextafter(fmin, 1), high=fmax / 1e17)

    def test_scalar_exception_propagation(self):
        # Tests that exceptions are correctly propagated in distributions
        # when called with objects that throw exceptions when converted to
        # scalars.
        #
        # Regression test for gh: 8865

        class ThrowingFloat(np.ndarray):
            def __float__(self):
                raise TypeError

        throwing_float = np.array(1.0).view(ThrowingFloat)
        assert_raises(TypeError, randomgen.mtrand.uniform, throwing_float, throwing_float)

        class ThrowingInteger(np.ndarray):
            def __int__(self):
                raise TypeError

        throwing_int = np.array(1).view(ThrowingInteger)
        assert_raises(TypeError, randomgen.mtrand.hypergeometric, throwing_int, 1, 1)

    def test_vonmises(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.vonmises(mu=1.23, kappa=1.54, size=(3, 2))
        desired = np.array([[2.28567572673902042, 2.89163838442285037],
                            [0.38198375564286025, 2.57638023113890746],
                            [1.19153771588353052, 1.83509849681825354]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_vonmises_small(self):
        # check infinite loop, gh-4720
        randomgen.mtrand.seed(self.seed)
        r = randomgen.mtrand.vonmises(mu=0., kappa=1.1e-8, size=10**6)
        np.testing.assert_(np.isfinite(r).all())

    def test_wald(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.wald(mean=1.23, scale=1.54, size=(3, 2))
        desired = np.array([[3.82935265715889983, 5.13125249184285526],
                            [0.35045403618358717, 1.50832396872003538],
                            [0.24124319895843183, 0.22031101461955038]])
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_weibull(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.weibull(a=1.23, size=(3, 2))
        desired = np.array([[0.97097342648766727, 0.91422896443565516],
                            [1.89517770034962929, 1.91414357960479564],
                            [0.67057783752390987, 1.39494046635066793]])
        assert_array_almost_equal(actual, desired, decimal=15)

    def test_weibull_0(self):
        randomgen.mtrand.seed(self.seed)
        assert_equal(randomgen.mtrand.weibull(a=0, size=12), np.zeros(12))
        assert_raises(ValueError, randomgen.mtrand.weibull, a=-0.)

    def test_zipf(self):
        randomgen.mtrand.seed(self.seed)
        actual = randomgen.mtrand.zipf(a=1.23, size=(3, 2))
        desired = np.array([[66, 29],
                            [1, 1],
                            [3, 13]])
        assert_array_equal(actual, desired)


class TestBroadcast(object):
    # tests that functions that broadcast behave
    # correctly when presented with non-scalar arguments
    def setup(self):
        self.seed = 123456789

    def setSeed(self):
        randomgen.mtrand.seed(self.seed)

    # TODO: Include test for randint once it can broadcast
    # Can steal the test written in PR #6938

    def test_uniform(self):
        low = [0]
        high = [1]
        uniform = randomgen.mtrand.uniform
        desired = np.array([0.53283302478975902,
                            0.53413660089041659,
                            0.50955303552646702])

        self.setSeed()
        actual = uniform(low * 3, high)
        assert_array_almost_equal(actual, desired, decimal=14)

        self.setSeed()
        actual = uniform(low, high * 3)
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_normal(self):
        loc = [0]
        scale = [1]
        bad_scale = [-1]
        normal = randomgen.mtrand.normal
        desired = np.array([2.2129019979039612,
                            2.1283977976520019,
                            1.8417114045748335])

        self.setSeed()
        actual = normal(loc * 3, scale)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, normal, loc * 3, bad_scale)

        self.setSeed()
        actual = normal(loc, scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, normal, loc, bad_scale * 3)

    def test_beta(self):
        a = [1]
        b = [2]
        bad_a = [-1]
        bad_b = [-2]
        beta = randomgen.mtrand.beta
        desired = np.array([0.19843558305989056,
                            0.075230336409423643,
                            0.24976865978980844])

        self.setSeed()
        actual = beta(a * 3, b)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, beta, bad_a * 3, b)
        assert_raises(ValueError, beta, a * 3, bad_b)

        self.setSeed()
        actual = beta(a, b * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, beta, bad_a, b * 3)
        assert_raises(ValueError, beta, a, bad_b * 3)

    def test_exponential(self):
        scale = [1]
        bad_scale = [-1]
        exponential = randomgen.mtrand.exponential
        desired = np.array([0.76106853658845242,
                            0.76386282278691653,
                            0.71243813125891797])

        self.setSeed()
        actual = exponential(scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, exponential, bad_scale * 3)

    def test_standard_gamma(self):
        shape = [1]
        bad_shape = [-1]
        std_gamma = randomgen.mtrand.standard_gamma
        desired = np.array([0.76106853658845242,
                            0.76386282278691653,
                            0.71243813125891797])

        self.setSeed()
        actual = std_gamma(shape * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, std_gamma, bad_shape * 3)

    def test_gamma(self):
        shape = [1]
        scale = [2]
        bad_shape = [-1]
        bad_scale = [-2]
        gamma = randomgen.mtrand.gamma
        desired = np.array([1.5221370731769048,
                            1.5277256455738331,
                            1.4248762625178359])

        self.setSeed()
        actual = gamma(shape * 3, scale)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, gamma, bad_shape * 3, scale)
        assert_raises(ValueError, gamma, shape * 3, bad_scale)

        self.setSeed()
        actual = gamma(shape, scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, gamma, bad_shape, scale * 3)
        assert_raises(ValueError, gamma, shape, bad_scale * 3)

    def test_f(self):
        dfnum = [1]
        dfden = [2]
        bad_dfnum = [-1]
        bad_dfden = [-2]
        f = randomgen.mtrand.f
        desired = np.array([0.80038951638264799,
                            0.86768719635363512,
                            2.7251095168386801])

        self.setSeed()
        actual = f(dfnum * 3, dfden)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, f, bad_dfnum * 3, dfden)
        assert_raises(ValueError, f, dfnum * 3, bad_dfden)

        self.setSeed()
        actual = f(dfnum, dfden * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, f, bad_dfnum, dfden * 3)
        assert_raises(ValueError, f, dfnum, bad_dfden * 3)

    def test_noncentral_f(self):
        dfnum = [2]
        dfden = [3]
        nonc = [4]
        bad_dfnum = [0]
        bad_dfden = [-1]
        bad_nonc = [-2]
        nonc_f = randomgen.mtrand.noncentral_f
        desired = np.array([9.1393943263705211,
                            13.025456344595602,
                            8.8018098359100545])

        self.setSeed()
        actual = nonc_f(dfnum * 3, dfden, nonc)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, nonc_f, bad_dfnum * 3, dfden, nonc)
        assert_raises(ValueError, nonc_f, dfnum * 3, bad_dfden, nonc)
        assert_raises(ValueError, nonc_f, dfnum * 3, dfden, bad_nonc)

        self.setSeed()
        actual = nonc_f(dfnum, dfden * 3, nonc)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, nonc_f, bad_dfnum, dfden * 3, nonc)
        assert_raises(ValueError, nonc_f, dfnum, bad_dfden * 3, nonc)
        assert_raises(ValueError, nonc_f, dfnum, dfden * 3, bad_nonc)

        self.setSeed()
        actual = nonc_f(dfnum, dfden, nonc * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, nonc_f, bad_dfnum, dfden, nonc * 3)
        assert_raises(ValueError, nonc_f, dfnum, bad_dfden, nonc * 3)
        assert_raises(ValueError, nonc_f, dfnum, dfden, bad_nonc * 3)

    def test_noncentral_f_small_df(self):
        self.setSeed()
        desired = np.array([6.869638627492048, 0.785880199263955])
        actual = randomgen.mtrand.noncentral_f(0.9, 0.9, 2, size=2)
        assert_array_almost_equal(actual, desired, decimal=14)

    def test_chisquare(self):
        df = [1]
        bad_df = [-1]
        chisquare = randomgen.mtrand.chisquare
        desired = np.array([0.57022801133088286,
                            0.51947702108840776,
                            0.1320969254923558])

        self.setSeed()
        actual = chisquare(df * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, chisquare, bad_df * 3)

    def test_noncentral_chisquare(self):
        df = [1]
        nonc = [2]
        bad_df = [-1]
        bad_nonc = [-2]
        nonc_chi = randomgen.mtrand.noncentral_chisquare
        desired = np.array([9.0015599467913763,
                            4.5804135049718742,
                            6.0872302432834564])

        self.setSeed()
        actual = nonc_chi(df * 3, nonc)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, nonc_chi, bad_df * 3, nonc)
        assert_raises(ValueError, nonc_chi, df * 3, bad_nonc)

        self.setSeed()
        actual = nonc_chi(df, nonc * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, nonc_chi, bad_df, nonc * 3)
        assert_raises(ValueError, nonc_chi, df, bad_nonc * 3)

    def test_standard_t(self):
        df = [1]
        bad_df = [-1]
        t = randomgen.mtrand.standard_t
        desired = np.array([3.0702872575217643,
                            5.8560725167361607,
                            1.0274791436474273])

        self.setSeed()
        actual = t(df * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, t, bad_df * 3)

    def test_vonmises(self):
        mu = [2]
        kappa = [1]
        bad_kappa = [-1]
        vonmises = randomgen.mtrand.vonmises
        desired = np.array([2.9883443664201312,
                            -2.7064099483995943,
                            -1.8672476700665914])

        self.setSeed()
        actual = vonmises(mu * 3, kappa)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, vonmises, mu * 3, bad_kappa)

        self.setSeed()
        actual = vonmises(mu, kappa * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, vonmises, mu, bad_kappa * 3)

    def test_pareto(self):
        a = [1]
        bad_a = [-1]
        pareto = randomgen.mtrand.pareto
        desired = np.array([1.1405622680198362,
                            1.1465519762044529,
                            1.0389564467453547])

        self.setSeed()
        actual = pareto(a * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, pareto, bad_a * 3)

    def test_weibull(self):
        a = [1]
        bad_a = [-1]
        weibull = randomgen.mtrand.weibull
        desired = np.array([0.76106853658845242,
                            0.76386282278691653,
                            0.71243813125891797])

        self.setSeed()
        actual = weibull(a * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, weibull, bad_a * 3)

    def test_power(self):
        a = [1]
        bad_a = [-1]
        power = randomgen.mtrand.power
        desired = np.array([0.53283302478975902,
                            0.53413660089041659,
                            0.50955303552646702])

        self.setSeed()
        actual = power(a * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, power, bad_a * 3)

    def test_laplace(self):
        loc = [0]
        scale = [1]
        bad_scale = [-1]
        laplace = randomgen.mtrand.laplace
        desired = np.array([0.067921356028507157,
                            0.070715642226971326,
                            0.019290950698972624])

        self.setSeed()
        actual = laplace(loc * 3, scale)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, laplace, loc * 3, bad_scale)

        self.setSeed()
        actual = laplace(loc, scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, laplace, loc, bad_scale * 3)

    def test_gumbel(self):
        loc = [0]
        scale = [1]
        bad_scale = [-1]
        gumbel = randomgen.mtrand.gumbel
        desired = np.array([0.2730318639556768,
                            0.26936705726291116,
                            0.33906220393037939])

        self.setSeed()
        actual = gumbel(loc * 3, scale)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, gumbel, loc * 3, bad_scale)

        self.setSeed()
        actual = gumbel(loc, scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, gumbel, loc, bad_scale * 3)

    def test_logistic(self):
        loc = [0]
        scale = [1]
        bad_scale = [-1]
        logistic = randomgen.mtrand.logistic
        desired = np.array([0.13152135837586171,
                            0.13675915696285773,
                            0.038216792802833396])

        self.setSeed()
        actual = logistic(loc * 3, scale)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, logistic, loc * 3, bad_scale)

        self.setSeed()
        actual = logistic(loc, scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, logistic, loc, bad_scale * 3)

    def test_lognormal(self):
        mean = [0]
        sigma = [1]
        bad_sigma = [-1]
        lognormal = randomgen.mtrand.lognormal
        desired = np.array([9.1422086044848427,
                            8.4013952870126261,
                            6.3073234116578671])

        self.setSeed()
        actual = lognormal(mean * 3, sigma)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, lognormal, mean * 3, bad_sigma)

        self.setSeed()
        actual = lognormal(mean, sigma * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, lognormal, mean, bad_sigma * 3)

    def test_rayleigh(self):
        scale = [1]
        bad_scale = [-1]
        rayleigh = randomgen.mtrand.rayleigh
        desired = np.array([1.2337491937897689,
                            1.2360119924878694,
                            1.1936818095781789])

        self.setSeed()
        actual = rayleigh(scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, rayleigh, bad_scale * 3)

    def test_wald(self):
        mean = [0.5]
        scale = [1]
        bad_mean = [0]
        bad_scale = [-2]
        wald = randomgen.mtrand.wald
        desired = np.array([0.11873681120271318,
                            0.12450084820795027,
                            0.9096122728408238])

        self.setSeed()
        actual = wald(mean * 3, scale)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, wald, bad_mean * 3, scale)
        assert_raises(ValueError, wald, mean * 3, bad_scale)

        self.setSeed()
        actual = wald(mean, scale * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, wald, bad_mean, scale * 3)
        assert_raises(ValueError, wald, mean, bad_scale * 3)
        assert_raises(ValueError, wald, 0.0, 1)
        assert_raises(ValueError, wald, 0.5, 0.0)

    def test_triangular(self):
        left = [1]
        right = [3]
        mode = [2]
        bad_left_one = [3]
        bad_mode_one = [4]
        bad_left_two, bad_mode_two = right * 2
        triangular = randomgen.mtrand.triangular
        desired = np.array([2.03339048710429,
                            2.0347400359389356,
                            2.0095991069536208])

        self.setSeed()
        actual = triangular(left * 3, mode, right)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, triangular, bad_left_one * 3, mode, right)
        assert_raises(ValueError, triangular, left * 3, bad_mode_one, right)
        assert_raises(ValueError, triangular, bad_left_two * 3, bad_mode_two, right)

        self.setSeed()
        actual = triangular(left, mode * 3, right)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, triangular, bad_left_one, mode * 3, right)
        assert_raises(ValueError, triangular, left, bad_mode_one * 3, right)
        assert_raises(ValueError, triangular, bad_left_two, bad_mode_two * 3, right)

        self.setSeed()
        actual = triangular(left, mode, right * 3)
        assert_array_almost_equal(actual, desired, decimal=14)
        assert_raises(ValueError, triangular, bad_left_one, mode, right * 3)
        assert_raises(ValueError, triangular, left, bad_mode_one, right * 3)
        assert_raises(ValueError, triangular, bad_left_two, bad_mode_two, right * 3)

        assert_raises(ValueError, triangular, 10., 0., 20.)
        assert_raises(ValueError, triangular, 10., 25., 20.)
        assert_raises(ValueError, triangular, 10., 10., 10.)

    def test_binomial(self):
        n = [1]
        p = [0.5]
        bad_n = [-1]
        bad_p_one = [-1]
        bad_p_two = [1.5]
        binom = randomgen.mtrand.binomial
        desired = np.array([1, 1, 1])

        self.setSeed()
        actual = binom(n * 3, p)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, binom, bad_n * 3, p)
        assert_raises(ValueError, binom, n * 3, bad_p_one)
        assert_raises(ValueError, binom, n * 3, bad_p_two)

        self.setSeed()
        actual = binom(n, p * 3)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, binom, bad_n, p * 3)
        assert_raises(ValueError, binom, n, bad_p_one * 3)
        assert_raises(ValueError, binom, n, bad_p_two * 3)

    def test_negative_binomial(self):
        n = [1]
        p = [0.5]
        bad_n = [-1]
        bad_p_one = [-1]
        bad_p_two = [1.5]
        neg_binom = randomgen.mtrand.negative_binomial
        desired = np.array([1, 0, 1])

        self.setSeed()
        actual = neg_binom(n * 3, p)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, neg_binom, bad_n * 3, p)
        assert_raises(ValueError, neg_binom, n * 3, bad_p_one)
        assert_raises(ValueError, neg_binom, n * 3, bad_p_two)

        self.setSeed()
        actual = neg_binom(n, p * 3)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, neg_binom, bad_n, p * 3)
        assert_raises(ValueError, neg_binom, n, bad_p_one * 3)
        assert_raises(ValueError, neg_binom, n, bad_p_two * 3)

    def test_poisson(self):
        max_lam = randomgen.mtrand.RandomState().poisson_lam_max

        lam = [1]
        bad_lam_one = [-1]
        bad_lam_two = [max_lam * 2]
        poisson = randomgen.mtrand.poisson
        desired = np.array([1, 1, 0])

        self.setSeed()
        actual = poisson(lam * 3)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, poisson, bad_lam_one * 3)
        assert_raises(ValueError, poisson, bad_lam_two * 3)

    def test_zipf(self):
        a = [2]
        bad_a = [0]
        zipf = randomgen.mtrand.zipf
        desired = np.array([2, 2, 1])

        self.setSeed()
        actual = zipf(a * 3)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, zipf, bad_a * 3)
        with np.errstate(invalid='ignore'):
            assert_raises(ValueError, zipf, np.nan)
            assert_raises(ValueError, zipf, [0, 0, np.nan])

    def test_geometric(self):
        p = [0.5]
        bad_p_one = [-1]
        bad_p_two = [1.5]
        geom = randomgen.mtrand.geometric
        desired = np.array([2, 2, 2])

        self.setSeed()
        actual = geom(p * 3)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, geom, bad_p_one * 3)
        assert_raises(ValueError, geom, bad_p_two * 3)

    def test_hypergeometric(self):
        ngood = [1]
        nbad = [2]
        nsample = [2]
        bad_ngood = [-1]
        bad_nbad = [-2]
        bad_nsample_one = [0]
        bad_nsample_two = [4]
        hypergeom = randomgen.mtrand.hypergeometric
        desired = np.array([1, 1, 1])

        self.setSeed()
        actual = hypergeom(ngood * 3, nbad, nsample)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, hypergeom, bad_ngood * 3, nbad, nsample)
        assert_raises(ValueError, hypergeom, ngood * 3, bad_nbad, nsample)
        assert_raises(ValueError, hypergeom, ngood * 3, nbad, bad_nsample_one)
        assert_raises(ValueError, hypergeom, ngood * 3, nbad, bad_nsample_two)

        self.setSeed()
        actual = hypergeom(ngood, nbad * 3, nsample)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, hypergeom, bad_ngood, nbad * 3, nsample)
        assert_raises(ValueError, hypergeom, ngood, bad_nbad * 3, nsample)
        assert_raises(ValueError, hypergeom, ngood, nbad * 3, bad_nsample_one)
        assert_raises(ValueError, hypergeom, ngood, nbad * 3, bad_nsample_two)

        self.setSeed()
        actual = hypergeom(ngood, nbad, nsample * 3)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, hypergeom, bad_ngood, nbad, nsample * 3)
        assert_raises(ValueError, hypergeom, ngood, bad_nbad, nsample * 3)
        assert_raises(ValueError, hypergeom, ngood, nbad, bad_nsample_one * 3)
        assert_raises(ValueError, hypergeom, ngood, nbad, bad_nsample_two * 3)

        assert_raises(ValueError, hypergeom, 10, 10, 25)

    def test_logseries(self):
        p = [0.5]
        bad_p_one = [2]
        bad_p_two = [-1]
        logseries = randomgen.mtrand.logseries
        desired = np.array([1, 1, 1])

        self.setSeed()
        actual = logseries(p * 3)
        assert_array_equal(actual, desired)
        assert_raises(ValueError, logseries, bad_p_one * 3)
        assert_raises(ValueError, logseries, bad_p_two * 3)

class TestThread(object):
    # make sure each state produces the same sequence even in threads
    def setup(self):
        self.seeds = range(4)

    def check_function(self, function, sz):
        from threading import Thread

        out1 = np.empty((len(self.seeds),) + sz)
        out2 = np.empty((len(self.seeds),) + sz)

        # threaded generation
        t = [Thread(target=function, args=(randomgen.mtrand.RandomState(s), o))
             for s, o in zip(self.seeds, out1)]
        [x.start() for x in t]
        [x.join() for x in t]

        # the same serial
        for s, o in zip(self.seeds, out2):
            function(randomgen.mtrand.RandomState(s), o)

        # these platforms change x87 fpu precision mode in threads
        if np.intp().dtype.itemsize == 4 and sys.platform == "win32":
            assert_array_almost_equal(out1, out2)
        else:
            assert_array_equal(out1, out2)

    def test_normal(self):
        def gen_random(state, out):
            out[...] = state.normal(size=10000)
        self.check_function(gen_random, sz=(10000,))

    def test_exp(self):
        def gen_random(state, out):
            out[...] = state.exponential(scale=np.ones((100, 1000)))
        self.check_function(gen_random, sz=(100, 1000))

    def test_multinomial(self):
        def gen_random(state, out):
            out[...] = state.multinomial(10, [1/6.]*6, size=10000)
        self.check_function(gen_random, sz=(10000, 6))

# See Issue #4263
class TestSingleEltArrayInput(object):
    def setup(self):
        self.argOne = np.array([2])
        self.argTwo = np.array([3])
        self.argThree = np.array([4])
        self.tgtShape = (1,)

    def test_one_arg_funcs(self):
        funcs = (randomgen.mtrand.exponential, randomgen.mtrand.standard_gamma,
                 randomgen.mtrand.chisquare, randomgen.mtrand.standard_t,
                 randomgen.mtrand.pareto, randomgen.mtrand.weibull,
                 randomgen.mtrand.power, randomgen.mtrand.rayleigh,
                 randomgen.mtrand.poisson, randomgen.mtrand.zipf,
                 randomgen.mtrand.geometric, randomgen.mtrand.logseries)

        probfuncs = (randomgen.mtrand.geometric, randomgen.mtrand.logseries)

        for func in funcs:
            if func in probfuncs:  # p < 1.0
                out = func(np.array([0.5]))

            else:
                out = func(self.argOne)

            assert_equal(out.shape, self.tgtShape)

    def test_two_arg_funcs(self):
        funcs = (randomgen.mtrand.uniform, randomgen.mtrand.normal,
                 randomgen.mtrand.beta, randomgen.mtrand.gamma,
                 randomgen.mtrand.f, randomgen.mtrand.noncentral_chisquare,
                 randomgen.mtrand.vonmises, randomgen.mtrand.laplace,
                 randomgen.mtrand.gumbel, randomgen.mtrand.logistic,
                 randomgen.mtrand.lognormal, randomgen.mtrand.wald,
                 randomgen.mtrand.binomial, randomgen.mtrand.negative_binomial)

        probfuncs = (randomgen.mtrand.binomial, randomgen.mtrand.negative_binomial)

        for func in funcs:
            if func in probfuncs:  # p <= 1
                argTwo = np.array([0.5])

            else:
                argTwo = self.argTwo

            out = func(self.argOne, argTwo)
            assert_equal(out.shape, self.tgtShape)

            out = func(self.argOne[0], argTwo)
            assert_equal(out.shape, self.tgtShape)

            out = func(self.argOne, argTwo[0])
            assert_equal(out.shape, self.tgtShape)

# TODO: Uncomment once randint can broadcast arguments
#    def test_randint(self):
#        itype = [bool, np.int8, np.uint8, np.int16, np.uint16,
#                 np.int32, np.uint32, np.int64, np.uint64]
#        func = randomgen.mtrand.randint
#        high = np.array([1])
#        low = np.array([0])
#
#        for dt in itype:
#            out = func(low, high, dtype=dt)
#            self.assert_equal(out.shape, self.tgtShape)
#
#            out = func(low[0], high, dtype=dt)
#            self.assert_equal(out.shape, self.tgtShape)
#
#            out = func(low, high[0], dtype=dt)
#            self.assert_equal(out.shape, self.tgtShape)

    def test_three_arg_funcs(self):
        funcs = [randomgen.mtrand.noncentral_f, randomgen.mtrand.triangular,
                 randomgen.mtrand.hypergeometric]

        for func in funcs:
            out = func(self.argOne, self.argTwo, self.argThree)
            assert_equal(out.shape, self.tgtShape)

            out = func(self.argOne[0], self.argTwo, self.argThree)
            assert_equal(out.shape, self.tgtShape)

            out = func(self.argOne, self.argTwo[0], self.argThree)
            assert_equal(out.shape, self.tgtShape)