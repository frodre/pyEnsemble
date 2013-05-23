import numpy as np


#######################################
# PostProcess.py
# This module houses the post processing module used to compile the hessian
# from the ensemble of runs. Created this mainly so it would be easy to 
# comment out in the event that no post processing is necessary.
#
# comm: mpi4py COMM_WORLD object for communication between nodes
# logger: python logging object for debug information
# emsPath: path to the EMS_SF_ADJ.OUT file
# numSims: number of simulations ran by the ensemble, only present for rank 0 process
# ppn: processors per node
# rank: rank of the running process
# fdDiff: finite differencing perturbation
#######################################

def compileHess(comm, logger, emsPath, numSims, ppn, rank, fdDiff, MPI):

	#Load in global sensitivity grid, and the location indices
	globSens = np.loadtxt(emsPath )
	locs = np.loadtxt('locations', dtype='int')
	
	if len(locs):
		#Grab locations from the global grid
		row = globSens[ locs[:,0] - 1, locs[:,1] - 1 ]
		dim = len(row)
	if not len(locs):
		logger.debug('No locations specified in location file.  No Hessian will be created.')
		pass
	elif rank == 0:
		assert len(locs) == numSims - 1, ('Number of locations provided does not match the number'
						  ' of simulations.  No heessian matrix being compiled.')
		logger.debug('Setting up base case matrix.')
		baseCase = np.zeros( (dim, dim) )
		for i in range(0, dim):
			baseCase[i,:] = row

		logger.debug('Setting up perturbed case matrix')
		pertCase = np.zeros( (dim, dim) )
		for i in range(1, numSims):
			row = comm.recv(source=i*ppn, tag=2)
			logger.debug('Received row from rank %i' % (i * ppn))
			pertCase[ i - 1, :] = row[0]

		hess = (pertCase - baseCase) / fdDiff

		logger.debug('Saving Hessian matrix to HESSIAN.OUT')
		np.savetxt('HESSIAN.OUT', hess, fmt='%16.8e')

	else:
		logger.debug('Sending row from %i' % (rank) )
		comm.send( [row, MPI.DOUBLE], dest=0, tag=2 )


