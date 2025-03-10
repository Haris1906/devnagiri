# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function

import sys
import argparse
import codecs
import cv2
import tensorflow as tf

import editdistance
from DataLoader import DataLoader, Batch
from Model import Model, DecoderType
from SamplePreprocessor import preprocess

import random
import numpy as np

# Disable eager execution
tf.compat.v1.disable_eager_execution()

class FilePaths:
    "filenames and paths to data"
    fnCharList = '../model/charList.txt'
    fnAccuracy = '../model/accuracy.txt'
    fnTrain = '../data/'
    fnInfer = '../data/3.jpg'
    fnCorpus = '../data/hindi_vocab.txt'

def train(model, loader):
    "train NN"
    epoch = model.lastEpoch  # Start from the last epoch
    bestCharErrorRate = float('inf')
    noImprovementSince = 0
    earlyStopping = 5
    while True:
        epoch += 1
        print('Epoch:', epoch)

        # train
        print('Train NN')
        loader.trainSet()
        while loader.hasNext():
            iterInfo = loader.getIteratorInfo()
            batch = loader.getNext()
            loss = model.trainBatch(batch)
            print('Batch:', iterInfo[0], '/', iterInfo[1], 'Loss:', loss)

        # validate
        charErrorRate = validate(model, loader)

        # if best validation accuracy so far, save model parameters
        if charErrorRate < bestCharErrorRate:
            print('Character error rate improved, save model')
            bestCharErrorRate = charErrorRate
            noImprovementSince = 0
            model.save(epoch)  # Pass the current epoch to save
            open(FilePaths.fnAccuracy, 'w').write(
                'Validation character error rate of saved model: %f%%' % (charErrorRate * 100.0))
        else:
            print('Character error rate not improved')
            noImprovementSince += 1

        # stop training if no more improvement in the last x epochs
        if noImprovementSince >= earlyStopping:
            print('No more improvement since %d epochs. Training stopped.' % earlyStopping)
            break

def validate(model, loader):
    "validate NN"
    print('Validate NN')
    loader.validationSet()
    numCharErr = 0
    numCharTotal = 0
    numWordOK = 0
    numWordTotal = 0
    while loader.hasNext():
        iterInfo = loader.getIteratorInfo()
        print('Batch:', iterInfo[0], '/', iterInfo[1])
        batch = loader.getNext()
        (recognized, _) = model.inferBatch(batch)

        print('Ground truth -> Recognized')
        for i in range(len(recognized)):
            numWordOK += 1 if batch.gtTexts[i] == recognized[i] else 0
            numWordTotal += 1
            dist = editdistance.eval(recognized[i], batch.gtTexts[i])
            numCharErr += dist
            numCharTotal += len(batch.gtTexts[i])
            print('[OK]' if dist == 0 else '[ERR:%d]' % dist, '"' + batch.gtTexts[i] + '"', '->',
                  '"' + recognized[i] + '"')

    # print validation result
    charErrorRate = numCharErr / numCharTotal
    wordAccuracy = numWordOK / numWordTotal
    print('Character error rate: %f%%. Word accuracy: %f%%.' % (charErrorRate * 100.0, wordAccuracy * 100.0))
    return charErrorRate

def infer(model, fnImg):
    "recognize text in image provided by file path"
    try:
        img = preprocess(cv2.imread(fnImg, cv2.IMREAD_GRAYSCALE), Model.imgSize)
        if img is None:
            raise Exception("Image could not be read")
        batch = Batch(None, [img])
        (recognized, probability) = model.inferBatch(batch, True)
        print('Recognized:', '"' + recognized[0].replace(" ", "") + '"')
        print('Probability:', probability[0])
    except Exception as e:
        print(f"Error during inference: {e}")

def infer_by_web(path, option):
    decoderType = DecoderType.BestPath
    if option == "bestPath":
        decoderType = DecoderType.BestPath
        print("Best Path Execute")
    if option == "beamSearch":
        decoderType = DecoderType.BeamSearch
    print(open(FilePaths.fnAccuracy).read())
    model = Model(codecs.open(FilePaths.fnCharList, encoding="utf8").read(), decoderType)
    img = preprocess(cv2.imread(path, cv2.IMREAD_GRAYSCALE), Model.imgSize)
    batch = Batch(None, [img])
    (recognized, probability) = model.inferBatch(batch, True)
    print('Recognized:', '"' + recognized[0].replace(" ", "") + '"')
    print('Probability:', probability[0])
    return recognized[0].replace(" ", ""), probability[0]

def main():
    "main function"
    # optional command line args
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", help="train the NN", action="store_true")
    parser.add_argument("--validate", help="validate the NN", action="store_true")
    parser.add_argument("--beamsearch", help="use beam search instead of best path decoding", action="store_true")
    parser.add_argument("--wordbeamsearch", help="use word beam search instead of best path decoding",
                        action="store_true")
    args = parser.parse_args()

    decoderType = DecoderType.BestPath
    if args.beamsearch:
        decoderType = DecoderType.BeamSearch
    elif args.wordbeamsearch:
        decoderType = DecoderType.WordBeamSearch

    # train or validate on IAM dataset
    if args.train or args.validate:
        # load training data, create TF model
        loader = DataLoader(FilePaths.fnTrain, Model.batchSize, Model.imgSize, Model.maxTextLen)

        # save characters of model for inference mode
        open(FilePaths.fnCharList, 'w', encoding='UTF-8').write(str().join(loader.charList))

        # save words contained in dataset into file
        open(FilePaths.fnCorpus, 'w', encoding='UTF-8').write(str(' ').join(loader.trainWords + loader.validationWords))

        # execute training or validation
        if args.train:
            model = Model(codecs.open(FilePaths.fnCharList, encoding='utf-8').read(), decoderType, mustRestore=False, lastEpoch=0)
            train(model, loader)
        elif args.validate:
            model = Model(codecs.open(FilePaths.fnCharList, encoding='utf-8').read(), decoderType, mustRestore=True, lastEpoch=0)
            validate(model, loader)

    # infer text on test image
    else:
        print(open(FilePaths.fnAccuracy).read())
        model = Model(codecs.open(FilePaths.fnCharList, encoding='utf-8').read(), decoderType, mustRestore=False)
        infer(model, FilePaths.fnInfer)

if __name__ == '__main__':
    main()
