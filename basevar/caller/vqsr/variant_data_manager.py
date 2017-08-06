"""
================================================
My own Gaussion Mixture Model for SV genotyping.
Learn form scikit-learn
================================================

Author: Shujia Huang
Date  : 2014-01-06 14:33:45

"""
import sys
import re
import os
import time

import numpy as np
from sklearn.metrics import roc_curve

from . import variant_recalibrator_argument_collection as VRAC
from . import variant_datum as vd
from .. import vcfutils


class VariantDataManager(object):

    def __init__(self, data=None):
        self.VRAC = VRAC.VariantRecalibratorArgumentCollection()
        self.annotationMean = None
        self.annotationSTD  = None
        self.annoTexts      = [['NR', 'Float', 'N ratio of ALT sequence'],
                               ['HR', 'Integer', 'Homozygous run'],
                               ['FS', 'Float', 'Phred-scaled p-value using '
                                'Fisher\'s exact test to detect strand bias']]

        self.data = [] # list <VariantDatum>
        if data: # data is not None
            if not isinstance(data[0],vd.VariantDatum):
                raise ValueError('[ERROR] The data type should be '
                                 '"VariantDatum" in VariantDataMa-'
                                 'nager(),but found %s'% str(type(data[0])))
            self.data = data
            for i, d in enumerate(self.data):
                self.data[i].annotations = np.array(self.data[i].annotations)

    def SetData(self, data):

        if not isinstance(data[0], vd.VariantDatum):
            raise ValueError('[ERROR] The data type should be "VariantDatum" '
                             'in VariantDataManager(),but found %s' %
                             str(type(data[0])))
        self.data = data
        for i, d in enumerate(self.data):
            self.data[i].annotations = np.array(d.annotations)

    def NormalizeData(self):

        data = np.array([d.annotations for d in self.data], dtype=float)
        mean = data.mean(axis=0)
        self.annotationMean = mean

        std  = data.std(axis=0)
        self.annotationSTD  = std

        # foundZeroVarianceAnnotation
        if any(std < 1e-5):
            raise ValueError('[ERROR] Found annotations with zero variance. '
                             'They must be excluded before proceeding.')

        # Each data now is (x - mean)/std
        for i, d in enumerate(data):

            self.data[i].annotations = (d - mean) / std
            # trim data by standard deviation threshold and mark failing data 
            # for exclusion later
            self.data[i].failingSTDThreshold = False
            if any(np.abs(self.data[i].annotations) > self.VRAC.STD_THRESHOLD):
                self.data[i].failingSTDThreshold = True

    def GetTrainingData(self):

        trainingData = [d for d in self.data if ((not d.failingSTDThreshold)
                                                 and d.atTrainingSite)]
        sys.stderr.write(('[INFO] Training with %d variants after standard '
                          'deviation thresholding.' % len(trainingData)))

        if len(trainingData) < self.VRAC.MIN_NUM_BAD_VARIANTS:
            sys.stderr.write(('[WARNING] Training with very few variant '
                              'sites! Please check the model reporting '
                              'PDF to ensure the quality of the model is '
                              'reliable.'))

        if len(trainingData) > self.VRAC.MAX_NUM_TRAINING_DATA:
            sys.stderr.write(('[WARING] Very large training set detected. '
                              'Downsampling to %d training variants.' %
                              self.VRAC.MAX_NUM_TRAINING_DATA))

            np.random.shuffle(trainingData) # Random shuffling
            return list(trainingData[i] 
                        for i in range(self.VRAC.MAX_NUM_TRAINING_DATA))

        return trainingData 

    def SelectWorstVariants(self, badLod):

        trainingData = []
        for i,d in enumerate(self.data):
            if(d.lod < badLod) and (not d.failingSTDThreshold):
                trainingData.append(d)
                # I do need: i order to be the same as self.data
                self.data[i].atAntiTrainingSite = True

        sys.stderr.write('[INFO] Training with worst %d scoring variants '
                         '--> variants with LOD < %.2f.' % (len(trainingData), badLod))

        if len(trainingData) > self.VRAC.MAX_NUM_TRAINING_DATA:
            sys.stderr.write('[WARING] Very large training set detected.'
                             'Downsampling to %d training variants.' %
                             self.VRAC.MAX_NUM_TRAINING_DATA)
            np.random.shuffle(trainingData) # Random shuffling
            return list(trainingData[i] for i in range(self.VRAC.MAX_NUM_TRAINING_DATA))

        return trainingData

    def CalculateWorstLodCutoff(self):

        lodThreshold, lodCum = None, []
        if len(self.data) > 0:

            lodDist = np.array([[d.atTrainingSite, d.lod] 
                                for d in self.data if(not d.failingSTDThreshold)])

            # I just use the 'roc_curve' function to calculate the worst 
            # LOD threshold, not use it to draw ROC curve And 'roc_curve' 
            # function will output the increse order, so that I don't 
            # have to sort it again
            _, tpr, thresholds = roc_curve(lodDist[:,0], lodDist[:,1]) 
            lodCum = [[thresholds[i], 1.0 - r] for i, r in enumerate(tpr)]

            for i, r in enumerate(tpr):
                if r > 1.0 - self.VRAC.POSITIVE_TO_NEGATIVE_RATE: 
                    lodThreshold = round(thresholds[i])
                    break

        return lodThreshold, np.array(lodCum)

def LoadTrainingSiteFromVCF(vcffile):
    """
    Just record the training site positions
    """

    if vcffile.endswith('.gz'):
        I = os.popen('gzip -dc %s' % vcffile)
    else:
        I = open(vcffile)

    sys.stderr.write('\n[INFO] Loading Training site from VCF %s\n' % time.asctime())
    n, dataSet =0, set()
    for line in I:
        n += 1
        if n % 100000 == 0:
            sys.stderr.write('** Loading lines %d %s\n' % (n, time.asctime()))

        if re.search(r'^#', line):
            continue

        col = line.strip().split()
        dataSet.add(col[0] + ':' + col[1])  # just get the positions

    I.close()
    sys.stderr.write('[INFO] Finish loading training set %d lines. %s\n' %
                     (n, time.asctime()))

    return dataSet

def LoadDataSet(vcfInfile, traningSet, pedFile=None):
    """
    Args:
        'pedFile': The .PED file
    """
    # Return a dict: [sample-id] => [parent1, parent2]
    # if pedFile is None, return {}
    pedigree = vcfutils.loadPedigree(pedFile)

    if len(traningSet) == 0:
        raise ValueError('[ERROR] No Training Data found')

    if vcfInfile.endswith('.gz'):
        I = os.popen('gzip -dc %s' % vcfInfile)
    else:
        I = open(vcfInfile)

    sys.stderr.write('\n[INFO] Loading data set from VCF %s\n' % time.asctime())
    n, data, hInfo = 0, [], vcfutils.Header()
    for line in I: # VCF format
        n += 1
        if n % 100 == 0:
            sys.stderr.write('** Loading lines %d %s\n' % (n, time.asctime()))

        col = line.strip().split()
        if re.search(r'^#CHROM', line):
            sam2col = {sam: i + 9 for i, sam in enumerate(col[9:])}

        # Record the header information
        if re.search(r'^#', line):
            hInfo.record(line.strip())
            continue

        qual = float(col[5])
        if qual == 5000 or qual == 10000:
            # do not use outline quality variants
            continue

        dp = re.search(r';?CM_DP=([^;]+)', col[7])
        fs = re.search(r';?FS=([^;]+)', col[7])
        if not dp or not fs:
            continue

        fs = round(float(fs.group(1)), 3)
        dp = round(float(dp.group(1)), 2)

        datum = vd.VariantDatum()
        # datum.raw_annotations = dict(QUAL=qual, DP=dp, FS=fs)
        # datum.annotations = [qual, dp, fs if fs != 0.0 else 0]

        datum.raw_annotations = dict(QUAL=qual, DP=dp)
        datum.annotations = [qual, dp]
        datum.variantOrder = col[0] + ':' + col[1]
        if datum.variantOrder in traningSet:
            datum.atTrainingSite = True

        data.append(datum)

    I.close()

    sys.stderr.write('[INFO] Finish loading data set %d lines. %s' %
                     (n, time.asctime()))

    return hInfo, np.array(data)

