
# coding: utf-8

# In[ ]:

import pandas
import numpy as np
import matplotlib.pyplot as plt
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import OneHotEncoder
import tensorflow as tf
import glob
import datetime
import itertools
from time import sleep


# In[ ]:

np.random.seed(1)


# In[ ]:

import os
import os.path
import gc


# In[ ]:

import argparse
parser = argparse.ArgumentParser(description = "Please insert the train flag")


# In[ ]:

parser.add_argument('-t', '--train', action = "store",
                    help='If true, we train and save. Else, otherwise.', required = True)


# In[ ]:

my_args = vars(parser.parse_args())
trainFlag = my_args['train']
trainFlag = trainFlag.lower() in ("True", "t", "true", "1", 1)


# In[ ]:

print datetime.datetime.now()
validFilePaths = []
for f in os.listdir("data/anomaly_data"):
    filePath = os.path.join("data/anomaly_data", f)
    if os.path.isdir(filePath):
        continue
    if os.stat(filePath).st_size <= 3:
        continue
    validFilePaths.append(filePath)
    
numF = int(1 * len(validFilePaths))
print 'Using this many files {0}'.format(numF)
validFilePaths = np.random.choice(validFilePaths, numF, replace=False)
df_list = (pandas.read_csv(f) for f in validFilePaths)
df = pandas.concat(df_list, ignore_index=True)
df = df[df['radiant_win'].notnull()]


# In[ ]:

print df.shape
columns = df.columns
df_catInteger_features_example = filter(lambda x: 'hero_id' in x, columns)


# In[ ]:

from itertools import chain
# these will require string processing on the column names to work
numericalFeatures = ['positive_votes', 'negative_votes', 'first_blood_time', 'radiant_win',
                    'duration', 'kills', 'deaths', 'assists', 'kpm', 'kda', 'hero_dmg',
                    'gpm', 'hero_heal', 'xpm', 'totalgold', 'totalxp', 'lasthits', 'denies',
                    'tower_kills', 'courier_kills', 'observer_uses', 'sentry_uses',
                    'ancient_kills', 'camps_stacked', 'abandons'] #apm problem
categoricalIntegerFeatures = ['hero_id']#['barracks_status', 'tower_status', 'hero_id'] 
                              #'item0', 'item1', 'item2', 'item3', 'item4', 'item5']
categoricalFullFeatures = ['patch']
numFeatures = [filter(lambda x: z in x, columns) for z in numericalFeatures]
categoricalIntegerFeatures  = [filter(lambda x: z in x, columns) for z in categoricalIntegerFeatures]
catFull = [filter(lambda x: z in x, columns) for z in categoricalFullFeatures]
numFeatures = list(chain(*numFeatures))
categoricalIntegerFeatures = list(chain(*categoricalIntegerFeatures))
catFull = list(chain(*catFull))


# In[ ]:

match_ids = df['match_id']
df_numerical = df[numFeatures]
df_numerical.loc[:, 'radiant_win'] = df_numerical.loc[:, 'radiant_win'].apply(lambda x : int(x))
df_numerical.iloc[:, 1:len(df_numerical.columns)] = df_numerical.iloc[:, 1:len(df_numerical.columns)].apply(lambda x: (x - np.nanmean(x)) / (np.nanmax(x) - np.nanmin(x)))
df_numerical = df_numerical.fillna(0)
df_numerical['radiant_win'] = df_numerical['radiant_win'].apply(lambda x: 1 if x >= 0 else 0)
df = df_numerical


# In[ ]:

x = np.random.rand(df.shape[0])
mask = np.where(x < 0.75)[0]
mask2 = np.where(x >= 0.75)[0]
df_train = df.iloc[mask, :]
df_test = df.iloc[mask2, :]
match_ids_train = match_ids.iloc[mask]
match_ids_test = match_ids.iloc[mask2]


# In[ ]:

NumFeatures = df.shape[1]
layer_size = [int(NumFeatures * 0.75), NumFeatures]


# In[ ]:

print NumFeatures


# In[ ]:

print df_train.shape


# In[ ]:

x = tf.placeholder(tf.float32, [None, NumFeatures])
y = x
#encoders
weights_1 = tf.Variable(tf.random_normal([NumFeatures, layer_size[0]], stddev = 1.0/NumFeatures/100), name='weights_1')
bias_1 = tf.Variable(tf.random_normal([layer_size[0]], stddev = 1.0/NumFeatures/100), name='bias_1')

#decoders
weights_2 = tf.Variable(tf.random_normal([layer_size[0], layer_size[1]], stddev = 1.0/NumFeatures/100), name='weights_2')
bias_2 = tf.Variable(tf.random_normal([layer_size[1]], stddev = 1.0/NumFeatures/100), name='bias_2')
  
layer1 = tf.tanh(tf.matmul(x, weights_1) + bias_1)
output = tf.tanh(tf.matmul(layer1, weights_2) + bias_2)

cost = tf.reduce_mean(tf.reduce_sum(tf.pow(y-output, 2), 1))
rank = tf.rank(cost)

learning_rate = 0.000001
beta1 = 0.5
beta2 = 0.5
optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate, beta1=beta1, beta2=beta2)
gradients, variables = zip(*optimizer.compute_gradients(cost))
gradients, _ = tf.clip_by_global_norm(gradients, 5.0)
train_op = optimizer.apply_gradients(zip(gradients, variables))
    
variable_dict = {'weights_1': weights_1, 'weights_2': weights_2,
                     'bias_1': bias_1, 'bias_2': bias_2}
saver = tf.train.Saver(variable_dict)
init = tf.global_variables_initializer()

ckpoint_dir = os.path.join(os.getcwd(), 'model-backups/model.ckpt')


# In[ ]:

flatten = lambda l: [item for sublist in l for item in sublist]
import requests
import json

def canIAnalyzeThisMatch(currentMatchID):
    host = "https://api.opendota.com/api/matches/" + str(currentMatchID)
    data = {'match_id': currentMatchID}
    data = requests.get(host, data)
    return data.status_code == 200

def test(sess, test_data):
    batch = test_data
    data = batch.as_matrix()
    data = data.astype(np.float32)
    layer1 = tf.tanh(tf.matmul(data, weights_1) + bias_1)
    output = tf.tanh(tf.matmul(layer1, weights_2) + bias_2)
    residuals = tf.reduce_sum(tf.abs(output - tf.cast(data, tf.float32)), axis = 1)
    output_results, residuals = sess.run([output, residuals])
    indices = np.argsort(residuals)[::-1]
    return data, output_results, indices, residuals


# In[ ]:

def train():
    numEpochs = 1000
    numBatches = 1000
    batchSize = int(round(0.01 * df_train.shape[0]))
    for epochIter in xrange(numEpochs):
        print 'Epoch: {0}'.format(epochIter)
        gc.collect()
        batch = df_train.sample(n=batchSize).as_matrix()
        temp_out = sess.run(cost, feed_dict = {x: batch})
        print temp_out
        if (epochIter+1) % 50 == 0:
            saver.save(sess, ckpoint_dir)
        for batchItr in xrange(numBatches):
            batch = df_train.sample(n=batchSize).as_matrix()
            sess.run(train_op, feed_dict = {x : batch})

with tf.Session() as sess:
    if sess.run(rank) != 0:
        raise Exception("Wrong dimenions of cost")
    if (trainFlag):
        sess.run(init)
        train()
    else:
        print 'Doing test'
        saver.restore(sess, ckpoint_dir)
        np.savetxt("data/weights1.csv", weights_1.eval(), delimiter=",")
        np.savetxt("data/bias1.csv", bias_1.eval(), delimiter=",")
        np.savetxt("data/weights2.csv", weights_2.eval(), delimiter=",")
        np.savetxt("data/bias2.csv", bias_2.eval(), delimiter=",")
        anomalies, output, indices_test, residuals = test(sess, df_test)
        anomaliesSave = anomalies[indices_test, :]
        output = output[indices_test, :]
        print anomalies[0, 0:10]
        print output[0, 0:10]
        np.savetxt("data/anomalies.csv", anomaliesSave, delimiter=",")
        np.savetxt("data/output.csv", output, delimiter=",")
        np.savetxt('data/indices.csv', indices_test, delimiter = ',')
        anomalizedAnalizable = match_ids_test.values
        goodMatches = []
        print len(anomalizedAnalizable)
        for i in range(len(anomalizedAnalizable)):
            an = anomalizedAnalizable[i]
            residual = residuals[i]
            goodMatches.append([int(an), residual])
        np.savetxt('data/goodAnomaliesResidual.csv', np.array(goodMatches), delimiter = ',')


# In[ ]:

print 'Done'
print datetime.datetime.now()


# In[ ]:



