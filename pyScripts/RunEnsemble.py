#/usr/bin/env python

# Script for running GEOS-Chem Adjoint Ensembles utilizing MPI4py

from mpi4py import MPI
import numpy as np
import os, sys, shutil, logging, InputGen, PostProcess as pp


#Set up logging
logging.basicConfig( format = '%(asctime)s [%(name)s] {%(levelname)s} %(name)s: %(message)s',
		     datefmt='%m-%d %H:%M:%S')
logger = logging.getLogger('pyEnsemble')

#Determines what level of messages are logged.  DEBUG for testing, ERROR for production
logger.setLevel(logging.DEBUG)




#Probably want to make this assertion more expressive (TODO)
try:
	assert len(sys.argv) == 5, "This script requires 4 input arguments to run."
except AssertionError, e:
	logger.critical(e)
	sys.exit()

#############
# simDir: directory of simulation to copy, e.g. /data/aperkins/pyEnsemble/gcadj_v33e_CH4/runs
# simFileDir: directory where input files, and exe are located relative to simDir
# simName:  name of the simulation being run, e.g. gcadj_v33e_CH4
# procPerNode: number of processors on each node of the high performance computer
# inputFule: name of the input file to be used in the input file generation script
#############


simDir = sys.argv[1]
simFileDir = sys.argv[2]
simName = sys.argv[3]
procPerNode = int(sys.argv[4])
inputFile = 'input.gcadj'
exeFile = os.path.join(simDir, simFileDir, 'geos')
fdDiff = 0.1


# actual communication agent
comm = MPI.COMM_WORLD

# number of total processors
size = comm.Get_size()

# current processor number
rank = comm.Get_rank()


#Manager node processes
if rank == 0:
	tStart = MPI.Wtime()
	numSims = size/procPerNode
	dst = os.path.join( simName, os.path.split(simDir)[1] )
	logger.debug( "Number of simulations: %d" % (numSims) )
	
	#Generate Input Files (e.g., input.gcadj.tmp01 )
	try:
		tmpInFiles, genMsg = InputGen.inFileGen(inputFile, numSims, fdDiff)
		logger.debug("Input files created: %s" % (tmpInFiles))
	except (IOError,AssertionError), e:
		logger.critical('Error generating input files: %s' % (e) )
		comm.Abort()

	if genMsg is not None:
		logger.warning(genMsg)

	dirSetupStart = MPI.Wtime()
	#Copy simulation to current ensemble directory
	try:	
		# Make new directory with same names as original simulation
		if not os.path.exists(simName):
			os.mkdir(simName)
			shutil.copytree(simDir, dst)
	except (OSError, IOError, Exception), e:
		logger.critical('Error copying simulation to ensemble directory: %s' % (e) )
		comm.Abort()

	#Move simulation files into distinct directories for each run
	simFileDir = os.path.join(dst, simFileDir)
	mainNodeDir = os.path.join( simFileDir, 'run_0' )
	
	if not os.path.exists(mainNodeDir):
		os.mkdir( mainNodeDir)
		
		#Moves all files and directories from simFileDir into the run_0 folder	
		for root, dirs, filenames in os.walk( simFileDir ):
			try:
				for dir in dirs:
					if not dir == 'run_0':
						shutil.move( os.path.join(root, dir), os.path.join(mainNodeDir, dir) )
						logger.debug('Moved %s to %s' % (os.path.join(root, dir), mainNodeDir) )
				for file in filenames:
					if not file == inputFile:
						shutil.move( os.path.join(root, file), os.path.join(mainNodeDir, file) )
						logger.debug('Moved %s to %s' % (os.path.join(root, file), mainNodeDir) )
			except Exception, e:
				logger.critical('Error copying main simulation into manager run directory: %s' % (e) )
				comm.Abort()	
	
			#Only want to copy first level
			break
	else:
		logger.debug('Copying exe file to existing manager node dir %s' % (mainNodeDir) )
	  	shutil.copy(exeFile, mainNodeDir)

	
	#Copy run_0 folder for each distinct remaining simulation
	for i in range(0, numSims):
		dir = os.path.join( simFileDir, 'run_%d' % (i) )
		try:
			if not i == 0:
				if not os.path.exists(dir):
					logger.debug('Copying simulation to %s' % (dir) )
					shutil.copytree(mainNodeDir, dir)
				else:
					logger.debug('Copying exe to existing simulation %s' % (dir) )
					shutil.copy(exeFile, dir)
			
			#Move unique input file to each run directory
			logger.debug('Copying input file %s to %s' % (tmpInFiles[i], dir) )
			shutil.move(tmpInFiles[i], os.path.join(dir, inputFile) )
			if not os.path.exists( os.path.join(dir, inputFile) ):
				logger.error('Error copying input file %s to %s' % (tmpInFiles[i], dir) )

			#Send run directory location to each other node
			if not i == 0:
				comm.send(dir, dest=i*procPerNode, tag=1)

		except Exception, e:
			logger.critical('Error copying directories for simulations: %s' % (e) )
			comm.Abort()

	logger.info('Directory setup time took %fs' % (MPI.Wtime() - dirSetupStart))
	dir = mainNodeDir

#Simulation starts on each node available
if rank % procPerNode == 0:
	
	name = MPI.Get_processor_name()
	
	#Recieve dir location from manager node
	if not rank == 0:
		dir = comm.recv(source=0, tag=1)
		logger.debug("%s - Received directory: %s" % (name, dir) )

	#Set an environmental variable $RUNID for use in the run script, different for each node
	try:
		ensSimDir = os.path.split(dir)[1]
		os.putenv("RUNID", ensSimDir)
		logger.debug("Environment variable for specific run set to %s" % (os.popen("echo $RUNID").read()) ) 
	except OSError, e:
		logger.error("Problem setting up environment on %s: %s" % (name, e) )

	#Run simulation
	try:
		logger.debug('Starting simulation on %s for %s' % (name, dir) )
		#same as typing command run > log into terminal
		os.system('%s > %s' % (os.path.join(dir, 'run'), os.path.join(dir, 'log') ) )
	
	except OSError, e:
		logger.error("Failed to start simulation on %s: %s" % (name, e) )
		
	#Post Process the Data
	try:
		logger.debug('Starting post processing of data.')
		emsPath = os.path.join(dir, 'EMS_SF_ADJ.OUT')
		if rank == 0:
			ppStart = MPI.Wtime()
			pp.compileHess(comm, logger, emsPath, numSims, procPerNode, rank, fdDiff, MPI)
			logger.info('Time to compile hessian: %fs' % (MPI.Wtime() - ppStart) )

			tEnd = MPI.Wtime()
			tTotal = (tEnd - tStart) 
			logger.info('Start time: %fs End time: %fs Total time: %fs' %(tStart, tEnd, tTotal) )
		else:
                        # note: rank 0 does all the work.  Here just calling the post processor 
                        # for completeness, but it won't do anything for the non-rank 0 threads
			pp.compileHess(comm, logger, emsPath, None, procPerNode, rank, fdDiff, MPI)
	except Exception, e:
		logger.critical("Problem post processing the data: %s" % (e))
		comm.Abort()

	logger.debug("End of RunEnsemble script on %s." % (name) )
