"""
Package for parse mpileup
Author: Shujia Huang
Date : 2016-07-19 14:14:21
"""
import re
import numpy as np

def rmStartEnd(bases):
    """
    remove start(`^`) and end(`$`) character

    Examples
    --------

    Base example

    >>> import mpileup
    >>> bases="...,$.$.$A,..A...,,,.,,...+5AGGC...-8GTCGG......,a,^F,^].^F,"
    >>> mpileup.clip(bases)
    ... ...,..A,..A...,,,.,,...+5AGGC...-8GTCGG......,a,,.,
    """
    return re.sub('\^\S|\$', '', bases)


def rmIndel(bases):
    """
    remove indels in pileup string

    Examples
    --------

    >>> import mpileup
    >>> bases="...,$.$.$A,..A...,,,.,,...+5AGGC...-8GTCGG......,a,^F,^].^F,"
    >>> mpileup.removeIndel(bases)
    ... ...,$.$.$A,..A...,,,.,,............,a,^F,^].^F,

    """
    return re.sub('[-+]\d+[ACGTacgtNn]+', '', bases)


def fetch_next(iter_fh):
    """
    re-define the next funtion in fetch function of pysam TabixFile()
    prevent throunghing the 'StopIteration'
    """

    if iter_fh == '': return ''

    try:
        line = iter_fh.next()
    except StopIteration:
        line = ''

    return line


def seek_position(target_pos, sample_line, sample_num, sample_tb_iter):

    ref_base = ''

    bases = ['N' for i in range(sample_num)]
    quals = ['!' for i in range(sample_num)]
    strand = ['.' for i in range(sample_num)]

    go_iter_mark = 0  # 1->iterate; 0->donot iterate or hit the end
    if sample_line:
        # chr2    181748  c       2       .,      EA
        tmp = sample_line.split('\t')
        pos = int(tmp[1])
        if pos == target_pos: # The same position

            ref_base = tmp[2]
            go_iter_mark = 1  # keep iterate
            for i in range(sample_num):
                try:
                    if tmp[3*(i + 1)] != '0' and tmp[3*(i+1)+1] != '*':
                       strand[i], bases[i], quals[i] = best_base(
                            tmp[2], tmp[3*(i+1)+1], tmp[3*(i+1)+2])

                except IndexError:
                    print >> sys.stderr, "[WARNING] IndexError", len(tmp), tmp

        elif pos < target_pos:

            while pos < target_pos:
                sample_line = fetch_next(sample_tb_iter)
                if sample_line:
                    tmp = sample_line.split('\t')
                    pos = int(tmp[1])
                else:
                    # The end of file. Break the loop.
                    break

            if pos == target_pos:
                ref_base = tmp[2]
                go_iter_mark = 1
                for i in range(sample_num):
                    if tmp[3*(i + 1)] != '0' and tmp[3*(i+1)+1] != '*':
                        strand[i], bases[i], quals[i] = best_base(
                            tmp[2], tmp[3*(i+1)+1], tmp[3*(i+1)+2])

        else:
            # pos > target_pos
            go_iter_mark = 0

    return sample_line, ref_base, bases, quals, strand, go_iter_mark


def best_base(ref_base, bases, quality):
    """Just get the best quality base for each sample.

    ignore the indels, '^' or '$'
    """
    b = rmIndel(rmStartEnd(bases))
    idx = np.argmax(quality) # get the best quality index

    ret_base = ref_base if b[idx] in [',', '.'] else b[idx]

    # Forwarstrand => +; reverseStrand => -.
    strand = '-' if (b[idx] == ',' or b[idx].islower()) else '+'
    return strand, ret_base.upper(), quality[idx]


def shuffle_base(ref_base, bases, quality):
    """

    ignore the indels, '^' or '$'
    """
    b = rmIndel(rmStartEnd(bases))
    idx = range(len(b))
    np.random.shuffle(idx)  # shuffle the index

    ret_base = ref_base if b[idx[0]] in [',', '.'] else b[idx[0]]

    # Forwarstrand => +; reverseStrand => -.
    strand = '-' if (b[idx[0]] == ',' or b[idx[0]].islower()) else '+'

    return strand, ret_base.upper(), quality[idx[0]]

