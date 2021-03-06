import os
import logging

import numpy as np

#####################
# function inFileGen(inputFile, flagFile, numGenFiles)
#
# inputFile: the input file template to be used
# flagFile: Variable flags and list of values to be used for replacement into inputFile
# numGenFiles: number of files to be generated, equivalent to number of simulations
#
# This function will take the input file template and copy it for each simulation
# being run.  There are flags in the input file which the function will look for and
# replace with numeric values.  
#####################

def inFileGen(inputFile, flagFile, numGenFiles):

	# Read first and second line of the flagList file to read flags 
	#  and their output format.
	
	logger = logging.getLogger('pyEnsemble.InputGen')
	logger.debug('Recieved inputFile %s' % inputFile)
	logger.debug('Recieved flagFile %s' % flagFile)
	
	exclude = ['\n', '\r']	
	flagList = []
	fmtList = []
	logger.info('Parsing flags for input file generation')
	try:
		f = open(flagFile, 'r')
		flagStr = f.readline()
		fmtStr = f.readline()
		flagStr = flagStr.split('\t')
		fmtStr = fmtStr.split('\t')
		for item in flagStr:
			if item and item not in exclude:
				item = item.strip('\n')
				item = item.strip('\r')
				item = item.strip(' ')
				flagList.append(item)
		for item in fmtStr:
			if item and item not in exclude:
                                item = item.strip('\n')
                                item = item.strip('\r')
                                item = item.strip(' ')
                                fmtList.append(item)
				
		f.close()

		logger.debug('Flaglist: %s' % flagList)
		logger.debug('Format list: %s' % fmtList)

	except IOError, e:
		logger.error(e)
		raise IOError('Could not read %s to obtain flags and values'\
			      % (flagFile))
	
	# Load rest of the values from the file
	numFlags = len(flagList)
	flagValues = np.loadtxt(flagFile, dtype='float', skiprows=2, ndmin=2)
	numVals = flagValues.shape[0] 
	
	if numVals > numGenFiles:
		msg = "More flag value rows provided than specified input files to be"\
		      "input files generated. Last %i locations omitted" \
		      % ( numVals - numGenFiles)
	elif numVals < numGenFiles:
		msg = ("Less flag value rows provided than total simulations. Used last "\
		       "row for  %i locations." % (numGenFiles - numVals) )
	else:
		msg = None
	
	
	# Generates a list of input file names that will be used
	outFile = os.path.split(inputFile)[1]
	inFileNames = [ '../tmp/%s.tmp%i' % (outFile, x) for x in range(0,numGenFiles) ]
	logger.debug('List of input files to create: %s', inFileNames)
	# For each input filename, open a file to write to, store file handler 
	#  pointers in a list
	inFiles = [ open(inFile, 'w') for inFile in inFileNames ]
	#Open the template file and copy each line to all input files	
	template = open(inputFile, 'r')
	for line in template:
		k = 0 
		for fh in inFiles:
			try:

				newLine = line
				if k < numVals:
                        	        for i in range(0, numFlags):
                	                        newLine = newLine.replace(flagList[i],\
        	                                  fmtList[i] % flagValues[k, i])
	                                fh.write(newLine)
					k = k + 1
				else:
	                                for i in range(0, numFlags):
        	                                newLine = newLine.replace(flagList[i],\
                	                          fmtList[i] % flagValues[k-1, i])
                        	        fh.write(newLine)


			except (IOError, IndexError), e:
				logger.error(e)
				raise IOError(e)

	for fh in inFiles:
		fh.close()

	template.close()
	return inFileNames, msg

