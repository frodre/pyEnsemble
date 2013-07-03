#/usr/bin/env python

# Script for running GEOS-Chem Adjoint Ensembles utilizing MPI4py
import os
import sys
import subprocess
import shutil
import logging
import ConfigParser

from mpi4py import MPI
import numpy as np

import InputGen

# Initialize communication between nodes and processors
comm = MPI.COMM_WORLD
# number of total processors
size = comm.Get_size()
# current processor number
rank = comm.Get_rank()

# Set up logging
logger = logging.getLogger('pyEnsemble')
logger.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s {%(levelname)s} %(name)s:'
                              ' %(message)s', datefmt='%m-%d %H:%M:%S')
sh.setFormatter(formatter)
sh.setLevel(logging.INFO)
logger.addHandler(sh)

# Retrieve number of processors per node from argument list
try:
        assert len(sys.argv) == 2, ('RunEnsemble requires 1 argument (ppn)'
    				    ' to be run. Please alter your job script'
				    ' accordingly.') 
except AssertionError, e:
        logger.critical(e)
	sys.exit(1)

procPerNode = int(sys.argv[1])

# Set up logging to file for each individual node
if rank % procPerNode == 0:
	logName = 'logs/%i.pyEnsemble.log' % (rank/procPerNode)
	fh = logging.FileHandler(logName, mode='w')
	fh.setLevel(logging.DEBUG)
	fh.setFormatter(formatter)
	logger.addHandler(fh)

################################################################################
# INPUT PARAMETER DESCRIPTIONS
################################################################################
# baseSimDir: directory of simulation to copy (should be far enough in to
#		exclude the code directory)
# simRunDir: directory where input files, and exe are located relative to
#	        baseSimDir
# codeDir: Location of code for compilation and exe file copying
# simName:  name of the simulation being run, e.g. gcadj_v33e_CH4
# procPerNode: number of processors on each node of HPC
# inputFiles: list of  input file locations to be copied into each run 
#		directory
# flagFiles: list of flag file locations to be used with corresponding input
#		files during the input file generation
################################################################################


# Load configuration file in the main process
if rank == 0:
	#Start timing for the ensemble
        tStart = MPI.Wtime()

	configFile = 'pyEnsemble.cfg'
	logger.info('Loading configuration file %s.' % (configFile))
	config = ConfigParser.ConfigParser()

	try:
		config.read(configFile)

		baseSimDir = config.get('filesystem', 'baseSimDir')
		simRunDir = config.get('filesystem', 'simRunDir')
		codeDir = config.get('filesystem', 'codeDir')
		simName = config.get('filesystem', 'simName')
		exeFilename= config.get('filesystem', 'exeFilename')

		inputFiles = config.get('inputFiles', 'GCFiles').split(',')
		flagFiles = config.get('inputFiles', 'flagFiles').split(',')
		
		assert len(inputFiles) == len(flagFiles), ('Number of input '
			'files in configuration file must be equal to the '
			'number of flag files')

		logger.info('Configuration file loading complete.')
		logger.debug('basesimDir = %s' % baseSimDir)
		logger.debug('simRunDir = %s' % simRunDir)
		logger.debug('codeDir = %s' % codeDir)
		logger.debug('simName = %s' % simName)
		logger.debug('exeFilename = %s' % exeFilename)

		for i in range(0, len(inputFiles) - 1):
			logger.debug('inputFile%s = %s' % (i, inputFiles[i]))
			logger.debug('flagFile%s = %s' % (i, flagFiles[i]))
					
		logger.debug('Number of input files generated for each'
			     ' simulation: %i' % len(inputFiles))

	except (ConfigParser.Error, AssertionError), e:
		logger.error(e)
		logger.critical('Failed to load the config file, cannot continue.')
		comm.Abort()

	numInFiles = len(inputFiles)
	numSims = size/procPerNode
	inputFNames = [ '%s' % (os.path.split(dir)[1]) for dir in inputFiles]
	dst = os.path.join( simName, os.path.split(baseSimDir)[1])
	logger.debug( "Number of simulations: %d" % (numSims))
	logger.debug( "Number of input files: %d" % (numInFiles))
	logger.debug( "Names of input files: %s" % (inputFNames))
        logger.debug("Destination for ensemble simulations: %s" % dst)
	
	#Generate Input Files (e.g., input.gcadj.tmp01 )
	logger.info('Beginning input file generation')
	try:
		tmpInFiles = []
		for i in range( 0, numInFiles):
			tmpList, genMsg = InputGen.inFileGen(inputFiles[i],
							     flagFiles[i],
							     numSims)
			logger.debug('tmpList: %s' % tmpList)
			tmpInFiles.append(tmpList)
			if genMsg is not None:
				logger.warning(genMsg)

		logger.info('Finished input file generation')
		logger.debug("Input files created: %s" % (tmpInFiles))

	except (IOError,AssertionError), e:
		logger.critical('Error generating input files: %s' % (e) )
		comm.Abort()

	dirSetupStart = MPI.Wtime() #Start time of dir copying

	# Copy simulation to current ensemble directory
	logger.info('Copying simulation to ensemble directory')
	try:	
		# Make new directory with same names as original simulation
		if not os.path.exists(simName):
			logger.debug('%s did not exist. Creating...' % simName)
			os.mkdir(simName)
		if not os.path.exists(dst):
			logger.debug('%s did not exist. Creating...' % dst)
			shutil.copytree(baseSimDir, dst)
		else:
			logger.debug('%s existed. No directories copied' % dst)
	except (OSError, IOError, Exception), e:
		logger.critical('Error copying simulation to ensemble'
		                ' directory: %s' % (e) )
		comm.Abort()

	# Move simulation files into distinct directories for each run
	logger.info('Moving simulation files into 0_run directory')
	simFileDir = os.path.join(dst, simRunDir)
	mainNodeDir = os.path.join( simFileDir, '0_run' )
	
	if not os.path.exists(mainNodeDir):
		os.mkdir( mainNodeDir)
		
		# Moves all files and directories from simFileDir into the run_0
		#  folder	
		for root, dirs, filenames in os.walk( simFileDir ):
			try:
				for dir in dirs:
					if not dir == '0_run':
						shutil.move(os.path.join(root, dir), 
								os.path.join(
									mainNodeDir,
									dir
								) 
							   )
						logger.debug('Moved %s to %s' %
							      (os.path.join(root, dir),
							       mainNodeDir) 
							    )
				for file in filenames:
					shutil.move( os.path.join(root, file),
						     os.path.join(mainNodeDir,
							 file
						     ) 
						   )
					logger.debug('Moved %s to %s' %
						      (os.path.join(root, file),
							mainNodeDir)
						     )
			except Exception, e:
				logger.critical('Error copying main simulation into'
						' manager run directory: %s' % (e))
				comm.Abort()	
	
			#Only want to copy first level
			break
	else:
		logger.info('Copying exe file to existing manager node dir %s'
			     % (mainNodeDir) )
		exeFileDir = os.path.join(baseSimDir, simRunDir, exeFilename)
	  	shutil.copy(exeFileDir, mainNodeDir)

	#Copy run_0 folder for each distinct remaining simulation
	logger.info('Creating run directories for each simulation')
	for i in range(0, numSims):
		dir = os.path.join(simFileDir, '%d_run' % (i))
		try:
			if not i == 0:
				if not os.path.exists(dir):
					logger.debug('Copying simulation to %s'
						     % (dir) )
					shutil.copytree(mainNodeDir, dir)
				else:
					logger.debug('Copying exe to existing '
						     'simulation %s' % (dir) )
					shutil.copy(exeFileDir, dir)
			
			#Move unique input file to each run directory
			for j in range(0, numInFiles):
				logger.debug('Copying input file %s to %s' % 
					     (tmpInFiles[j][i], dir))
				shutil.move(tmpInFiles[j][i],
					    os.path.join(dir, inputFNames[j]))

				if not os.path.exists( os.path.join(dir, inputFNames[j]) ):
					logger.error('Error copying input file %s to %s'
					     	% (tmpInFiles[j][i], dir))

			#Send run directory location to each other node
			if not i == 0:
				comm.send(dir, dest=i*procPerNode, tag=1)

		except Exception, e:
			logger.critical('Error copying directories for'
					' simulations: %s' % (e))
			comm.Abort()

	logger.info('Directory setup time took %fs' % (MPI.Wtime() - dirSetupStart))
	dir = mainNodeDir #mainNodeDir is the run directory for 0_run

#Simulation starts on each node available
if rank % procPerNode == 0:
	name = MPI.Get_processor_name()
	
	#Recieve dir location from manager node
	if not rank == 0:
		dir = comm.recv(source=0, tag=1)
		logger.debug("%s - Received directory: %s" % (name, dir) )

	#Set an environmental variable $RUNID for use in the run script, different
	# for each node
	try:
		ensSimDir = os.path.split(dir)[1]
		os.putenv("RUNID", ensSimDir)
		logger.debug("Environment variable for specific run set to %s"
			     % (os.popen("echo $RUNID").read()) ) 
	except OSError, e:
		logger.error("Problem setting up environment on %s: %s" % (name, e) )

	#Run simulation
	try:
		logger.debug('Starting simulation on %s for %s' % (name, dir) )
		#same as typing command run > log into terminal
		runloc = os.path.join(dir, 'run')
		logloc = os.path.join(dir, 'log')
		runProc = subprocess.call([runloc, '>', logloc], shell=False)
	
	except OSError, e:
		logger.error("Failed to start simulation on %s: %s" % (name, e) )
		
	#Post Process the Data
#	try:
#		logger.debug('Starting post processing of data.')
#		emsPath = os.path.join(dir, 'EMS_SF_ADJ.OUT')
#		if rank == 0:
#			ppStart = MPI.Wtime()
#			pp.compileHess(comm, logger, emsPath, numSims, procPerNode, rank, fdDiff, MPI)
#			logger.info('Time to compile hessian: %fs' % (MPI.Wtime() - ppStart) )
#
#			tEnd = MPI.Wtime()
#			tTotal = (tEnd - tStart) 
#			logger.info('Start time: %fs End time: %fs Total time: %fs' %(tStart, tEnd, tTotal) )
#		else:
#                        # note: rank 0 does all the work.  Here just calling the post processor 
#                        # for completeness, but it won't do anything for the non-rank 0 threads
#			pp.compileHess(comm, logger, emsPath, None, procPerNode, rank, fdDiff, MPI)
#	except Exception, e:
#		logger.critical("Problem post processing the data: %s" % (e))
#		comm.Abort()

	logger.info("End of RunEnsemble script on %s." % (name) )
