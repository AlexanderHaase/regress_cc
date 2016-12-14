#!/usr/bin/python3

#
# Regress compiler options that may cause issues
#

import yaml
import subprocess
import itertools
import contextlib
import os
import os.path
import sys
import datetime
import argparse
import shlex
import functools
import logging

logger = logging.getLogger( __name__ if __name__ != '__main__' else os.path.basename( sys.argv[ 0 ] ) )

class Optimizers( object ):
	'''
	Collection of gcc optimizer configurations given a command line
	'''

	@classmethod 
	def fromArgs( cls, args, cc = 'gcc' ):
		'''
		Ask gcc to tell us about optimizers given a command line. Discards
		options without defaults.
		'''
		try:
			proc = subprocess.run( itertools.chain( ( cc, ), args, ( '-Q',  '--help=optimizers' ) ), stdout = subprocess.PIPE, stderr = subprocess.PIPE, check = True )
			lines = proc.stdout.decode( "utf-8" ).splitlines()
			return cls( dict( filter( lambda pair: len( pair ) is 2 and pair[ 0 ].startswith( '-f' ),  map( str.split, lines ) ) ), args, cc )
		except subprocess.SubprocessError as e:
			raise e

	def __init__( self, options, args, cc = 'gcc' ):
		self.options = options
		self.args = args
		self.cc = cc

	def flatten( self ):
		'''
		Flatten an optimizer dictionary into an argv iterable
		'''
		implied = self.fromArgs( self.args, self.cc )
		delta = filter( lambda pair: pair[ 1 ] != '[default]', implied.diff( self ) )

		def transform( pair ):
			if pair[ 1 ] == '[enabled]':
				return pair[ 0 ]
			elif pair[ 1 ] == '[disabled]':
				return pair[ 0 ].replace( '-f', '-fno-', 1 )
			else:
				return ''.join( pair )

		return itertools.chain( self.args, map( transform, delta ) )

	def diff( self, other ):
		'''
		Extract the differing options between two Optimizer sets
		'''

		return filter( lambda pair: self.options[ pair[ 0 ] ] != pair[ 1 ], other.options.items() )

	@classmethod
	def regress( cls, base, reach, testOptions ):
		'''
		Permutate through the two optimizers and return a third
		'''
		result = cls( base.options, reach.args, base.cc )

		for key, value in base.diff( reach ):
	
			original = result.options[ key ]
			result.options[ key ] = value

			logger.info( "Testing optimizer '{}' change '{}' => '{}'...".format( key, original, value ) )

			try:
				testOptions( result.flatten() )
				logger.info( "PASS optimizer '{}' change '{}' => '{}'.".format( key, original, value ) )

			except subprocess.SubprocessError as e:
				result.options[ key ] = original
				logger.info( "FAIL optimizer '{}' change '{}' => '{}':\n\t{}".format( key, original, value, "\n\t".join( e.stdout.decode( "utf-8" ).splitlines() ) ) )

		return result

def testPredicate( predicate, separator, fmt, timeout, options ):
	'''
	Parse and format the predicate, then evaluate each command.
	'''
	formated = predicate.format( separator.join( map( fmt.format, options ) ) )
	tokens = shlex.split( formated )


	# split stream at ';' tokens
	cmds = [ [] ]
	argv = cmds[ 0 ]
	for token in tokens:
		if token == ';':
			argv = []
			cmds.append( argv )
		else:
			argv.append( token )

	for index, cmd in enumerate( cmds, 1 ):
		logger.debug( "Predicate Evaluation {:4d}/{}: {}".format( index, len( cmds ), cmd ) )
		subprocess.run( cmd, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, check = True, timeout = timeout )
	

if __name__ == '__main__':
	parser = argparse.ArgumentParser( description = "Regress gcc optimizer behavior using the provided predicate. Given two sets of compiler options, it detects relevant implicit options and incrementally tests differences between both options. Tests are one or more template commands that indicate failure via non-zero return status.\n\tMake example: {} --begin='-Og', --end='-Ofast -fno-inine' --predicate='CFLAGS=\"{{}}\" make myTest ; ./myTest'".format( sys.argv[ 0 ] ),
epilog = "After testing, predicate-passing arguments are written to stdout." )

	parser.add_argument( '-b', '--begin',
		type = str,
		required = True,
		help = "Options beginning regression, should pass predicate" )

	parser.add_argument( '-e', '--end',
		type = str,
		required = True,
		help = "Options ending regression." )

	parser.add_argument( '-c', '--compiler',
		type = str,
		default = 'gcc',
		help = "Compiler to use." )

	parser.add_argument( '-p', '--predicate',
		type = str,
		required = True,
		help = "Predicate for testing compiler arguments. Template is brace expanded and shell interpreted: 'gcc {} -o test test.c; ./test' => 'gcc -finline-functions -o test test.c; ./test' The command should return non-zero on error." )

	parser.add_argument( '-s', '--arg-separator',
		type = str,
		default = " ",
		help = "Separator for arguments supplied to predicate." )

	parser.add_argument( '-f', '--arg-format',
		type = str,
		default = "{}",
		help = "Format for arguments supplied to predicate, brace expanded." )

	parser.add_argument( '-t', '--timeout', 
		type = int,
		default = None,
		help = "Timeout for predicate, in seconds." )

	parser.add_argument( '-v', '--verbose',
		type = str,
		default = 'WARN',
		choices = (' DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL' ),
		help = "Verbosity for logging." )

	args = parser.parse_args()
	handler = logging.StreamHandler()
	handler.setLevel( args.verbose )
	handler.setFormatter( logging.Formatter( '%(asctime)s - %(name)s - %(levelname)s - %(message)s' ) )
	logger.addHandler( handler )
	logger.setLevel( args.verbose )

	working = Optimizers.regress(
		Optimizers.fromArgs( shlex.split( args.begin ), args.compiler ),
		Optimizers.fromArgs( shlex.split( args.end ), args.compiler ),
		functools.partial( testPredicate, args.predicate, args.arg_separator, args.arg_format, args.timeout ) )
	
	print( args.arg_separator.join( working.flatten() ) )
	
