
cdef extern from "include/em.h" nogil:
    void cEM(double * init_allele_freq, double * ind_allele_likelihood, double * marginal_likelihood, double * expect_allele_prob, int nsample, int ntype, int iter_num, double epsilon)

cdef extern from "include/ranksum.h" nogil:
    double cRankSums(double * x, int n1, double * y, int n2)

cdef extern from "include/kfunc.h" nogil:
    double kt_fisher_exact(int n11, int n12, int n21, int n22, double * _left, double * _right, double * two)

# cpdef ref_vs_alt_ranksumtest(char ref_base, char alt_base, list data)

# cpdef strand_bias(char ref_base, list alt_base, list bases, list strands)

# cpdef EM(double[::1] init_allele_freq, double[:,::1] ind_allele_likelihood, double[::1] marginal_likelihood, double[::1] expect_allele_prob)
