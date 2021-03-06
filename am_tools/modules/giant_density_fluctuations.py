import json
import os
import sys
from itertools import product
from time import sleep
from zipfile import ZipFile, BadZipFile

import matplotlib.pyplot as plt
from numpy import multiply, concatenate, array, zeros, savetxt, mean, std, sqrt, linspace, float32, all, arange, divide, empty, append
from fast_histogram import histogram2d
from pandas import read_csv, DataFrame, concat, io
from tqdm import tqdm
import multiprocessing
import warnings
"""
Local package installation: python -m pip install --user -e am_tools/
"""


class GiantDensityFluctuations:
	"""
	This class provides functions for data loading and for actual calculations of giant density fluctuations.
	"""
	@staticmethod
	def load_raw_file(fp_, file_, chs=100000, ci=(2, 3), dt=float32, file_known=False, file_l=None, verbose=False):
		"""
		This function reads required data from the file_ or, when all data is zipped, from file in data.zip.
		:param fp_: file path template
		:param file_: file name
		:param chs: the size of a single data chunk
		:param ci: column indices
		:param dt: data type
		:param file_known: a parameter showing if there is any knowledge about the data file size
		:param file_l: if file_known is true, this is the file length
		:param verbose: if True the function describes the process of file loading, including possible errors
		:return: a pandas dataframe or None if there is no data to read/the data is corrupted
		"""
		file_path = fp_ % file_
		col_names = ('x', 'y')
		if not os.path.isfile(file_path):
			if not os.path.isfile(fp_ % 'data.zip'):
				verbose and print("\nNo (un)zipped data, skipping.\n")
				return None
			else:
				try:
					with ZipFile(fp_ % 'data.zip'):
						pass
				except BadZipFile:
					verbose and print("Corrupted zip, skipping. ")
					return None
				resulting_file = ZipFile(fp_ % 'data.zip').open(file_)
		else:
			try:
				read_csv(file_path, sep='\s+', engine='c', nrows=1)
			except io.common.EmptyDataError:
				verbose and print("\n%s is empty, skipping.\n" % file_)
				return None
			resulting_file = file_path

		verbose and print("\nLoading the file, this might take some time\n")
		df_, dt_ = DataFrame(), dict((x, dt) for x in col_names)
		if file_known:
			index = 0
			for x in read_csv(resulting_file, sep='\s+', engine='c', usecols=ci, names=col_names, dtype=dt_, chunksize=chs):
				df_ = concat([df_, x], ignore_index=True)
				index += 1
				sys.stdout.write("\rChunk %d/~%d" % (index, file_l))
		else:
			for x in read_csv(resulting_file, sep='\s+', engine='c', usecols=ci, names=col_names, dtype=dt_, chunksize=chs):
				df_ = concat([df_, x], ignore_index=True)
		verbose and print("\nDone.\n")
		return df_

	@staticmethod
	def average_number_density(population, domain_size, bin_size):
		"""
		This function calculates the average number density per bin
		:param population: integer, the total number of particles
		:param domain_size: a tuple that contains the sizes of a rectangular domain
		:param bin_size: a tuple that contains the sizes of a single bin
		:return: float, average number of particles per bin i.e., number density,
		n_bins, an array containing the number of bins in x and y directions
		"""
		if len(domain_size) != len(bin_size):
			raise ValueError("Incorrect domain or binning parameters, exiting.")
		else:
			n_bins = (int(domain_size[0] / bin_size[0]), int(domain_size[1] / bin_size[1]))
			factor = 1 / (n_bins[0] * n_bins[1])
			return factor * population, n_bins

	@staticmethod
	def get_bin_number(domain_size, bin_size):
		"""
		This function calculates the average number density per bin
		:param domain_size: a tuple that contains the sizes of a rectangular domain
		:param bin_size: a tuple that contains the sizes of a single bin
		:return: n_bins, an array containing the number of bins in x and y directions
		"""
		if len(domain_size) != len(bin_size):
			raise ValueError("Incorrect domain or binning parameters, exiting.")
		else:
			n_bins = (int(domain_size[0] / bin_size[0]), int(domain_size[1] / bin_size[1]))
			return n_bins

	@staticmethod
	def density_fluctuations(x, y, av_density, range_, edges):
		"""
		This function calculates giant density fluctuations using provided particle positions and bin edges
		:param x: x coordinate of particles
		:param y: y coordinate of particles
		:param av_density: average bin density
		:param range_: the range of x, y coordinates. By default the lower bound is 0, thus only the upper bound is provided
		:param edges: bin edges
		:return: the normalized value of density fluctuations
		"""
		h = histogram2d(x, y, range=[[0, range_[0]], [0, range_[1]]], bins=[edges[0], edges[1]])
		e_n_squared = mean(h*h)
		e_squared_n = av_density * av_density
		deviation = sqrt(e_n_squared - e_squared_n)
		normed_deviation = deviation / sqrt(av_density)
		return normed_deviation

	@staticmethod
	def density_fluctuations1(x, y, average_density, range_, n_bins_):
		"""
		This function calculates giant density fluctuations using provided particle positions and bin edges.
		*NOTE*: this particular version of the algorithm is sub-optimal i.e., it is possible to make it faster
		by finding the square of a histogram first and then finding its mean. However, due to usage of a less precise
		alternative (some particles can be missing in the histogram) to the numpy histogram2d that might result
		in negative values of the variance.
		Thus, we subtract the mean value first and find the square next potentially having slightly incorrect results.
		However, large datasets should not suffer from this significantly.
		FIXME try to use the number of particles in all bins instead od system population. Check how fast it is.
		:param x: x coordinate of particles
		:param y: y coordinate of particles
		:param average_density: average number of particles per bin
		:param range_: the range of x, y coordinates. By default the lower bound is 0, thus only the upper bound is provided
		:param n_bins_: number of bins in x,y directions
		:return: the normalized value of density fluctuations
		"""
		h = histogram2d(x, y, range=[[0, range_[0]], [0, range_[1]]], bins=[n_bins_[0], n_bins_[1]])
		h -= average_density
		h *= h # squared std is marked as variance
		normed_std = sqrt(mean(h) / average_density)
		return normed_std

	@staticmethod
	def mean_density_per_bin(total_x, total_y, range_, n_bins_, n_samples):
		h = histogram2d(total_x, total_y, range=[[0, range_[0]], [0, range_[1]]], bins=[n_bins_[0], n_bins_[1]])
		return h / n_samples

	@staticmethod
	def density_variations(sample_x, sample_y, range_, n_bins_, mean_density_squared):
		h = histogram2d(sample_x, sample_y, range=[[0, range_[0]], [0, range_[1]]], bins=[n_bins_[0], n_bins_[1]])
		h *= h
		var_ = h - mean_density_squared
		return var_


class GDFanalysis(GiantDensityFluctuations):
	def __init__(self):
		self.pop = None
		self.size_x = None
		self.size_y = None
		self.data_path = None
		self.min_range = None
		self.max_range = None
		self.fn = None
		self.default_values = {
			"size_x": 120.0,
			"size_y": 12.0,
			"population": 961,
			"path": None,
			"filename": "simulation.main.data.bin",
			"verbose": False,
			"cluster": False,
			"min_range": 1,
			"max_range": 100,
			"samples": 10000}
		self.verbose = False
		self.cluster = False
		self.samples = None

	def get_parameters(self):
		"""
		All parameters for the simulations are provided as an external JSON string,
		actual usage looks like this:
		echo  '{"path": "/path/%s"}' | python script.py
		:return: None
		"""
		try:
			sys_par = json.load(sys.stdin)
			if type(sys_par) is not dict:
				raise ValueError('Incorrect input format, should be a JSON string')
		except json.JSONDecodeError as e:
			raise e

		if "path" in sys_par:
			self.data_path = sys_par["path"]
		else:
			raise ValueError("No data path provided, exiting.")

		self.pop = sys_par["population"] if "population" in sys_par else self.default_values["population"]
		self.size_x = sys_par["size_x"] if "size_x" in sys_par else self.default_values["size_x"]
		self.size_y = sys_par["size_y"] if "size_y" in sys_par else self.default_values["size_y"]
		self.fn = sys_par["filename"] if "filename" in sys_par else self.default_values["filename"]
		self.verbose = sys_par["verbose"] if "verbose" in sys_par else self.default_values["verbose"]
		self.cluster = sys_par["cluster"] if "cluster" in sys_par else self.default_values["cluster"]
		self.samples = sys_par["samples"] if "samples" in sys_par else self.default_values["samples"]
		
		if self.cluster:
			self.min_range = sys_par["min_range"] if "min_range" in sys_par else self.default_values["min_range"]
			self.max_range = sys_par["max_range"] if "max_range" in sys_par else self.default_values["max_range"]
		return None

	@staticmethod
	def generate_bin_sizes(domain_shape='rectangle', domain_sizes=None):
		#FIXME add two parameters allowing passing the bins
		"""
		Basic function that retuns bin sizes for the default confinement geometry
		:return: two arrays, each of them contains bin sizes in the corresponding direction
		"""
		if domain_shape == 'rectangle':
			dxarr = array([0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7.5, 10, 12, 15, 20, 24, 30, 40, 60])
			#dyarr = array([0.5, 0.75, 1, 1.5, 2, 3, 4, 6])
			y_fr = [1/24, 1/16, 1/12, 1/8, 1/6, 1/4, 1/3, 1/2]
			dyarr = multiply(y_fr, domain_sizes[1])
			bin_sizes = [bp for bp in product(dxarr, dyarr)]
			#n_ = arange(1, 51)
			#channel_fractions = divide(1, n_)
			#bin_sizes = [tuple([fraction * d_size for d_size in domain_sizes]) for fraction in channel_fractions]
			#bin_sizes = [tuple([13 * fraction, 13 * fraction]) for fraction in channel_fractions]
			#f1 = [0.01, 0.02, 0.04, 0.05, 0.1, 0.2, 0.5, 1]
			#f2 = [0.01, 0.02, 0.04, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 1/24, 1/16, 1/12, 1/8, 1/6, 1/3]
			#xbinsizes = multiply(f1, domain_sizes[0])
			#xbinsizes = concatenate((xbinsizes, array([0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10, 15, 20, 30])))
			#ybinsizes = multiply(f2, domain_sizes[1])
			#bin_sizes_ = [()] * (len(xbinsizes) * len(ybinsizes))
			#for i, el in enumerate(product(xbinsizes, ybinsizes)):
			#	bin_sizes_[i] = el
			#bin_sizes = bin_sizes_
			#bin_sizes = concatenate((bin_sizes, bin_sizes_))
			#print(bin_sizes)
			return bin_sizes
		elif domain_shape == 'disk':
			raise ValueError('Unsupported domain type')
		elif domain_shape == 'square':
			raise ValueError('Unsupported domain type')
		else:
			raise ValueError('Unsupported domain type')

		# TODO replace this function
		# f1 = [0.01, 0.02, 0.04, 0.05, 0.1, 0.2, 0.5, 1]
		# f2 = [0.01, 0.02, 0.04, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 1/24, 1/16, 1/12, 1/8, 1/6, 1/3]
		# xbinsizes = multiply(f1, self.size_x)
		# ybinsizes = multiply(f2, self.size_y)
		# xbinsizes = concatenate((xbinsizes, array([0.5, 0.75, 1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10, 15, 20, 30])))
		#return xbinsizes, ybinsizes

	def general_sub_pipeline(self, df_, bins):
		"""
		This function goes through the provided number of samples and calculates density fluctuations for
		all provided bin sizes
		:param df_: a pandas dataframe
		:param bins: array of tuples, each of them contains bin sizes
		:return: an array containing the resulting data
		"""
		resulting_data = zeros((2, 1))
		x_v, y_v = df_['x'].to_numpy(), df_['y'].to_numpy()  # turn to numpy first, it's ~2 times faster
		#x_v = x_v if all(x_v >= 0) else x_v + self.size_x / 2
		#y_v = y_v + 0.5 if all(y_v >= 0) else y_v + self.size_y / 2  # FIXME need a solution for the variety of data
		iterator = tqdm(bins, total=len(bins)) if self.verbose else bins

		domain_size_t = (self.size_x, self.size_y)
		print("data transformed")
		for count, bin_dim_t in enumerate(iterator):
			bin_number = self.get_bin_number(domain_size=domain_size_t, bin_size=bin_dim_t)
			mean_density_array = self.mean_density_per_bin(total_x=x_v, total_y=y_v, range_=domain_size_t, n_bins_=bin_number, n_samples=self.samples)
			mean_density_sq = mean_density_array * mean_density_array
			average_density_variation = zeros(bin_number)
			for i in range(self.samples):
				i_min, i_max = i * self.pop, (i + 1) * self.pop
				d_var = self.density_variations(sample_x=x_v[i_min:i_max], sample_y=y_v[i_min:i_max], range_=domain_size_t, n_bins_=bin_number, mean_density_squared=mean_density_sq)
				average_density_variation += d_var
			average_density_variation /= self.samples

			cell_count = average_density_variation.shape[0] * average_density_variation.shape[1]
			partial_result = zeros((2, cell_count))
			#print(partial_result.shape)
			#print(mean_density_array)
			#print(average_density_variation)
			#print(mean_density_array.shape, average_density_variation.shape)
			for cumul_index in range(cell_count):
				x_index, y_index = cumul_index // average_density_variation.shape[1], cumul_index % average_density_variation.shape[1]
				partial_result[0][cumul_index], partial_result[1][cumul_index] = mean_density_array[x_index][y_index], average_density_variation[x_index][y_index]
				#print(x_index, y_index)
			# TODO more pythonic way
			# FIXME zeros

			#print("\n\n\n\n\n")
			#print(resulting_data)
			#print(partial_result)
			resulting_data = append(resulting_data, partial_result, axis=1)
		#print(resulting_data.shape)
		#print(resulting_data)
		return resulting_data

	@staticmethod
	def data_reduce(data):
		pass

	@staticmethod
	def extract_exponent(data):
		pass

	@staticmethod
	def save_proc_data(data, save_path):
		"""
		Saves the resulting array.
		:param data: array name
		:param save_path: path to the file
		:return: None
		"""
		savetxt(save_path % "gdf_processed_data.txt", data.T, fmt='%.6e')
		return None

	@staticmethod
	def plot_figure(data, save_path):
		"""
		Plots a gdf figure and saves it.
		:param data: data to plot
		:param save_path: path to the figure
		:return: None
		"""
		plt.figure()
		plt.yscale('log')
		plt.xscale('log')
		plt.errorbar(data[2, :], data[3, :], yerr=data[4, :], fmt='o')
		plt.savefig(save_path % "plot.png")
		plt.close()
		return None

	@staticmethod
	def check_data_size(df_, population, n_samples):
		"""
		This function provides a simple check for initial data.
		The total number of entries in the dataframe has to be greater or equal to
		the product of the number of particles and the number of samples.

		:param df_: a pandas dataframe to check
		:param population: the number of elements in a given system, integer
		:param n_samples: the number of snapshots, integer
		:return: None
		"""
		total_data_length = len(df_.index)
		assert population * n_samples <= total_data_length, "Incomplete data/incorrect parameters"
		return None

	def serial_data_pipeline(self):
		"""
		This function is a pipeline for serial data processing.
		It gets parameters, collects and processes the corresponding data.
		:return: None
		"""
		self.get_parameters()
		bins = self.generate_bin_sizes(domain_sizes=(self.size_x, self.size_y))
		df = self.load_raw_file(self.data_path, self.fn, verbose=self.verbose)
		if df is None:
			raise ValueError("No data provided!")
		self.check_data_size(df, self.pop, self.samples)
		data = self.general_sub_pipeline(df, bins)
		self.save_proc_data(data, self.data_path)
		self.plot_figure(data, self.data_path)
		return None

	def parallel_data_pipeline_single_file(self):
		pass

	def parallel_data_pipeline_multiple_files(self):
		pass
