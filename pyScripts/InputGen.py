#/usr/bin/env python

import os, numpy as np

#####################
# function inFileGen(inputFile, numGenFiles)
#
# inputFile : the input file template to be used
# numGenFiles: number of files to be generated, equivalent to number of simulations
#
# This function will take the input file template and copy it for each simulation
# being run.  There are flags in the input file which the function will look for and
# replace with numeric values.  Right now all that is supported is altering the model
# grid cell latitude, and longitude indexes. Location indexes should be placed in a tab
# delimited file named 'locations' in the pyEnsemble directory.  
#####################

def inFileGen(inputFile, numGenFiles, fdDiff):
	locations = np.loadtxt('locations', dtype='int')

	try:
		assert os.path.exists(inputFile)
	except:
		raise IOError('%s not found in current directory' % (inputFile) )

	numLocs = len(locations)

	# numGenFiles - 1 because first simulation is base case
	if numLocs > numGenFiles - 1:
		msg = "More locations provided than input files generated.  Last %i locations omitted" \
		      % ( numLocs - numGenFiles)
	elif numLocs < numGenFiles - 1:
		msg = ("Less locations provided than input files generated. Used default location of LATIDX 32"
		       " LONIDX 41 for %i locations." % (numGenFiles - numLocs) )
	else:
		msg = None
	
	
	# Generates a list of input file names that will be used
	inFileNames = [ '%s.tmp%i' % (inputFile, x) for x in range(0,numGenFiles) ]
	# For each input filename, open a file to write to, store file handler pointers in a list
	inFiles = [ open(inFile, 'w') for inFile in inFileNames ]
	
	#Open the template file and copy each line to all input files	
	template = open(inputFile, 'r')
	for line in template:
		k = -1
		for fh in inFiles:
			try:
				#If k = -1 it's base case simulation only need FD_DIFF set to 0
				if k == -1:
					newLine = line.replace('#FDDIFF', str(0))
					newLine = newLine.replace('#LATIDX', str(32))
					newLine = newLine.replace('#LONIDX', str(41))
					fh.write(newLine)
					k = 0

				#Depending on the number of locations provided, may have to fill in 
				#files using a default location
 				elif k < numLocs:
					
					#Look for the flags and replace with unique location identifiers
					newLine = line.replace('#LATIDX', str(locations[k,1]) )
					newLine = newLine.replace('#LONIDX', str(locations[k,0]) )
					newLine = newLine.replace('#FDDIFF', str(fdDiff))
					fh.write(newLine)
					k = k + 1

				else:
					
					newLine = line.replace('#LATIDX', str(32))
					newLine = newLine.replace('#LONIDX', str(41))
					newLine = newLine.replace('#FDDIFF', str(fdDiff))
					fh.write(newLine)

			except IOError, e:
				raise IOError(e)

	for fh in inFiles:
		fh.close()

	template.close()
	return inFileNames, msg


