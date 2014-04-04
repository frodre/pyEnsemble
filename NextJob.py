import os
import numpy as np

optData = '/lustre/janus_scratch/wape2190/pyEnsemble/gcadj_v33e_CH4_GCEns/runs/v8-02-01/geos5/1_run/OptData'

iters = []

for filename in  os.listdir(optData):

	tmp = filename.split('.')
	print tmp	
	iter = int(tmp[len(tmp) - 1])
	iters.append(iter)

iters = np.asarray(iters)

max = np.amax(iters)

tmpRun = '/lustre/janus_scratch/wape2190/pyEnsemble/inFiles/tmpRun'
runDir = '/projects/wape2190/runs/CH4/gcadj_v33e_CH4_GCEns/runs/v8-02-01/geos5/run'

f = open(tmpRun, 'r')
run = open(runDir, 'w')

for line in f:
	 
	newline = line.replace('#START', str(max + 1))
	newline = newline.replace('#END', str(max + 1))
	run.write(newline)

f.close()
run.close()
