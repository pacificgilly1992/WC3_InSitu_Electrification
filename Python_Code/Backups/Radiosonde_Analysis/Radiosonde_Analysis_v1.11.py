from __future__ import absolute_import, division, print_function

__project__ = "Electrical Pre-Conditioning of Convective Clouds"
__title__ = "Plotting Radiosonde Data"
__author__ = "James Gilmore"
__email__ = "james.gilmore@pgr.reading.ac.uk"
__version__ = "1.11"
__date__ = "24/01/2019"
__status__ = "Stable"
__changelog__ = "Added in Hypothesis methods"

# Standard libraries
import os
import sys
import time
import warnings
import glob
import argparse

# Data analysis modules
import numpy as np
import scipy as sp
import pandas as pd

# Plotting modules
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from matplotlib.ticker import MaxNLocator

# Datetime handelling modules
from datetime import datetime, timedelta

sys.path.insert(0, '/home/users/th863480/PhD/Global_Functions')

#User Processing Modules
import Gilly_Utilities as gu

#Data Set-up Modules
from Data_Importer import EPCC_Importer
from Data_Quality import Radiosonde_Checks_v2 as Radiosonde_Checks
from Data_Output import SPRadiosonde, CrossCorrelation_Scatter_Plot, Back2Back_Histogram

#Import Global Variables
import PhD_Config as PhD_Global

#Import Tephigram Plotter
from Extras.Tephigram import Tephigram as SPTephigram

#Import WC3 Extras (for GPS2UTC)
from Extras.WC3_Extras import GPS2UTC, CloudDrift, Radiosonde_Launch

class Radiosonde(EPCC_Importer, Radiosonde_Checks, SPRadiosonde, SPTephigram):
	"""
	This class will process all the data aquired from a radiosonde output the data in various forms,
	including, height plot, tepihgram and indicies.
	
	Parameters
	----------
	EPCC_Importer : class
		Used to import other datasets other than the actual radiosonde
	Radiosonde_Checks : class
		Used to quality control the radiosonde data
	SPRadiosonde : class
		Used to plot the radiosonde data
`	SPTephigram : class
		Used to plot the tepihgram of the data
	"""
	
	def __init__(self, sensor_package, height_range, calibrate='Counts', reload=False, verbose=False):
		"""
		Set-up radiosonde data.
		
		Parameters
		----------
		sensor_package : int
			The sensor package number flown for the PhD.
		height_range : array_like
			The height range used to limit the data. Must be array_like with two elements
			specifying the lower and upper bands in kilometres. 
			
			e.g. height_range = (<lower_bound_in_km>, <upper_bound_in_km>),
		calibrate : str, optional
			The type of data to plot. Either 'Counts', 'Volts' or 'Units' are acceptable.
		reload : bool, optional
			Specify whether to re-process the radiosonde data. N.B. if data has not
			already proccessed at the particular height_range specified, the data will
			be reprocessed.
		verbose : bool, optional
			Specify whether to output extra information about the processing to the 
			console.
		"""
		
		############################################################################
		"""Prerequisites"""
    
		# Time Controls
		t_begin = time.time()
		
		# Error Checks
		if sensor_package is None: sys.exit("[Error] You must specify either the sensor_package number")
		if height_range is None: sys.exit("[Error] You must specify either the height_range number")
		
		# Storage Locations
		self.Storage_Path    		= PhD_Global.Storage_Path_WC3
		self.Processed_Data_Path	= 'Processed_Data/Radiosonde/'
		self.Raw_Data_Path			= 'Raw_Data/'
		self.Radiosonde_Plots_Path  = 'Plots/Radiosonde/'
		self.Tephigram_Plots_Path   = 'Plots/Tephigram/'
		
		# Bound classes
		self.importer = EPCC_Importer()
		self.sensor_package = str(sensor_package)
		self.height_range = height_range
		self.calibrate = calibrate
		self.reload = reload
		self.verbose = verbose
		self.data = PhD_Global.Data
		
		# Real name for all Pandora Channels for each radiosonde launch
		self.RawChannelList = {
			0: ['Lin', 'Log', 'Cyan/PLL', 'IR', 'Parity'],
			1: ['Lin', 'Log', 'Cyan/PLL', 'IR', 'Parity'],
			2: ['Lin', 'Log', 'Cyan/PLL', 'IR', 'Parity'],
			3: ['Lin', 'Log', 'Cyan/PLL', 'IR', 'Parity'],
			4: ['Lin', 'Log', 'Cyan/PLL', 'IR', 'Parity'],
			5: ['Lin', 'Log', 'Cyan/PLL', 'IR', 'Parity'],
			6: ['Lin', 'Log/Turbulence', 'Cyan', 'IR/Parity'], # Not Launched Yet
			7: ['Lin', 'Log/Turbulence', 'Cyan', 'IR/Parity'], # Not Launched Yet
			8: ['Lin', 'Log/Turbulence', 'Cyan', 'IR/Parity'], # Not Launched Yet
			9: ['Lin', 'Log', 'Cyan', 'IR', 'Turbulence'],
			10: ['Lin', 'Log', 'Cyan', 'IR', 'Turbulence']
			}
		
		# Number of bits (2^n)
		self.NumofBits = {
			0: 12,
			1: 12,
			2: 12,
			3: 12,
			4: 12,
			5: 12,
			6: 16, # Not Launched Yet
			7: 16, # Not Launched Yet
			8: 16, # Not Launched Yet
			9: 12,
			10: 12
			}
		
		# Launch Time (UTC)
		self.LaunchTime = {
			0: "N/A",
			1: "N/A",
			2: "N/A",
			3: np.datetime64("2018-05-24 15:10:00"),
			4: np.datetime64("2018-05-31 15:38:30"), # np.datetime64("2018-05-31 14:20:00"), 
			5: np.datetime64("2018-07-27 15:39:00"),
			6: None, # Not Launched Yet
			7: None, # Not Launched Yet
			8: None, # Not Launched Yet
			9: np.datetime64("2018-12-05 16:12:00"),
			10: np.datetime64("2018-12-05 09:22:30")
			}
		
		# Reading University Atmospheric Observatory Coordinates
		self.RUAO_Coords = (51.441491, -0.937897)
		
		############################################################################
		
		# Import Radiosonde Data
		self.Radiosonde_Data, self.Launch_Datetime, self.Radiosonde_File = self._RadiosondeImporter('All')
	
		# Identify clouds within data
		self.Clouds_ID, self.LayerType = self._CloudIdentifier('All')
		Clouds_ID = self.Clouds_ID.copy()
	
		# Calculate the space charge density using the log charge sensor
		# self.Calibration_Log = self._ChargeCalibrator(self.calibrate, self.sensor_package, self.Clouds_ID, self.LayerType) if np.any(np.in1d(self.calibrate, ['Volts', 'Units'])) else None
		
	def _RadiosondeImporter(self, Sensor_Package=None):
		"""
		Check and Import Data
		"""
		
		# Error check that either Radiosonde_File or Sensor_Package has been specified
		if Sensor_Package is None: sys.exit("[Error] You must specify either the Sensor_Package number")
		
		t1 = time.time()
		
		Sensor_Package = [3,4,5,6,7,8,9,10] if Sensor_Package == 'All' else [Sensor_Package]
		
		Radiosonde_Data_All = {}
		Launch_Datetime_All = {}
		Radiosonde_File_All = {}
		for sensor in Sensor_Package:
			
			if self.verbose is True: print("[INFO] Loading Sensor No.%s" % sensor)
			
			# First check if any NumPy processed files are available for this sensor package
			file_check = glob.glob(self.Storage_Path + self.Processed_Data_Path + 'Radiosonde_Flight_No.' + str(sensor).rjust(2,'0') + '_*/Radiosonde_Flight_PhD_James_No.' + str(sensor) + '*.npy')
			
			tester = ['No.' + str(sensor), str(self.height_range[0]) + 'km', str(self.height_range[1]) + 'km']
			if np.any(gu.string_checker(file_check, tester, condition='all')) and self.reload is False:
				
				if self.verbose is True: print("[INFO] Getting radiosonde data from file")
				
				# Find correct file to import
				Radiosonde_File_All[str(sensor)] = file_check[gu.bool2int(gu.string_checker(file_check, tester, condition='all'))[0]]
				
				# Load data using careful method (see: https://stackoverflow.com/a/45661259/8765762)
				Radiosonde_Data = np.load(Radiosonde_File_All[str(sensor)]).item()
				
				# Load GPS data
				tester = ['No.' + str(sensor), 'GPSdata']
				self.GPS_File = file_check[gu.bool2int(gu.string_checker(file_check, tester, condition='all'))[0]]
				GPS_Data = np.load(self.GPS_File)
				
				# Estimate the launch time from the data
				GPS_Data = GPS_Data[~np.isnan(GPS_Data['SondeX'])]
				Launch_Datetime = GPS2UTC(GPS_Data['GPS_Week'][0], GPS_Data['GPS_Second'][0])
					
			else:
				
				if self.verbose is True: print("[INFO] Processing radiosonde data from scratch")
				
				# Attempt to find the radiosonde file either directly or from glob
				Radiosonde_File = glob.glob(self.Storage_Path + self.Processed_Data_Path + 'Radiosonde_Flight_No.' + str(sensor).rjust(2,'0') + '_*/Radiosonde_Flight_PhD_James_No.' + str(sensor) + '*a.txt')
				
				# If no radiosonde file was found we end program
				if (len(Radiosonde_File) == 0) and (len(Sensor_Package) > 1): 
					if self.verbose is True: print("[Warning] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (sensor))
					continue
				# else:
					# sys.exit("[Warning] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (sensor))
					
				# If the radiosonde file was found via glob we need to convert to str from list
				if isinstance(Radiosonde_File, list): Radiosonde_File_All[str(sensor)] = Radiosonde_File[0]
				
				# Once the radiosonde file is found we can attempt to find the GPS file in the raw file section
				self.GPS_File = glob.glob(self.Storage_Path + self.Raw_Data_Path + 'Radiosonde_Flight_No.' + str(sensor).rjust(2,'0') + '_*/GPSDCC_RESULT*.tsv')
				
				# Import all the data		
				Radiosonde_Data =  pd.read_csv(Radiosonde_File_All[str(sensor)], 
					sep=r"\s*", 
					header=None, 
					engine='python',
					names=('time', 
					'height', 
					'P', 
					'Tdry', 
					'RH',
					self.RawChannelList[sensor][0],
					self.RawChannelList[sensor][1],
					self.RawChannelList[sensor][2],
					self.RawChannelList[sensor][3],
					self.RawChannelList[sensor][4],
					'long',
					'lat',
					'range',
					'bearing',
					'Tdew',
					'u',
					'v',
					'MR'), 
					dtype={'time': np.float64, 
					'height': np.float64, 
					'P': np.float64, 
					'Tdry': np.float64, 
					'RH': np.float64, 
					self.RawChannelList[sensor][0]: np.float64, 
					self.RawChannelList[sensor][1]: np.float64, 
					self.RawChannelList[sensor][2]: np.float64, 
					self.RawChannelList[sensor][3]: np.float64, 
					self.RawChannelList[sensor][4]: np.float64, 
					'long': np.float64, 
					'lat': np.float64, 
					'range': np.float64, 
					'bearing': np.float64, 
					'Tdew': np.float64, 
					'u': np.float64, 
					'v': np.float64, 
					'MR': np.float64},
					na_values=-32768, 
					comment='#', 
					index_col=False).to_records(index=False)
						
				GPS_Data =  pd.read_csv(self.GPS_File[0], sep="\t",
					skiprows=51, 
					header=None, 
					usecols=(1,2,4),
					names=('GPS_Week', 
					'GPS_Second', 
					'SondeX'), 
					dtype={'GPS_Week': np.int32, 
					'GPS_Second': np.float64, 
					'SondeX': np.float64},
					na_values=-32768, 
					comment='#', 
					index_col=False).to_records(index=False) if len(self.GPS_File) != 0 else None
				
				# Fix np.recarray issue
				Radiosonde_Data = gu.fix_recarray(Radiosonde_Data)
				GPS_Data = gu.fix_recarray(GPS_Data)
				
				# Estimate the launch time from the data
				if self.GPS_File is not None: 
					GPS_Data = GPS_Data[~np.isnan(GPS_Data['SondeX'])]
					Launch_Datetime = GPS2UTC(GPS_Data['GPS_Week'][0], GPS_Data['GPS_Second'][0])
						
				# Calibrate Height, Temperature and Convert PANDORA channels from counts to volts if required.
				Radiosonde_Cal_Counts = Radiosonde_Checks(
					data=Radiosonde_Data.copy(), 
					calibrate=None, 
					package_no=sensor,
					height_range=self.height_range, 
					bits=self.NumofBits[sensor], 
					verbose=self.verbose)
					
				Radiosonde_Cal_Volts = Radiosonde_Checks(
					data=Radiosonde_Data.copy(), 
					calibrate='Volts', 
					package_no=sensor, 
					height_range=self.height_range, 
					bits=self.NumofBits[sensor], 
					verbose=self.verbose)
					
				Radiosonde_Cal_Units = Radiosonde_Checks(
					data=Radiosonde_Data.copy(), 
					calibrate='Units',
					package_no=sensor, 
					height_range=self.height_range, 
					bits=self.NumofBits[sensor], 
					verbose=self.verbose)
					
				# Calibrate RH
				Radiosonde_Cal_Counts.RH()
				Radiosonde_Cal_Volts.RH()
				Radiosonde_Cal_Units.RH()
				
				# Calibrate Cloud Sensor
				Radiosonde_Cal_Counts.Cloud(method='offset')
				Radiosonde_Cal_Volts.Cloud(method='offset')
				Radiosonde_Cal_Units.Cloud(method='offset')
				
				# Calibrate Charge
				Radiosonde_Cal_Volts.Charge()
				Radiosonde_Cal_Units.Charge(lab_calibration=True)
				
				# Calibrate Vibrating Wire
				Radiosonde_Cal_Volts.PLL()
				Radiosonde_Cal_Units.PLL()
				
				# Nest Radiosonde_Cal into Radiosonde_Data
				Radiosonde_Data = {'Date' : np.datetime64(Launch_Datetime).astype('datetime64[s]'),
									'Raw' : Radiosonde_Data,
									'Counts' : Radiosonde_Cal_Counts.finalise(),
									'Volts' : Radiosonde_Cal_Volts.finalise(),
									'Units' : Radiosonde_Cal_Units.finalise()}	
				
				# Save Radiosonde_Data to file. N.B. numpy is not perfect for saving dictionaries. Becareful when loading data again!
				Save_Loc = self.Storage_Path + self.Processed_Data_Path + 'Radiosonde_Flight_No.' + \
					str(sensor).rjust(2,'0') + '_' + Launch_Datetime.strftime('%Y%m%d') + \
					'/Radiosonde_Flight_PhD_James_No.' + str(sensor) + '_' + Launch_Datetime.strftime('%Y%m%d') + \
					'_' + str(self.height_range[0]) + 'km_to_' + str(self.height_range[1]) + 'km_Ascent.npy'
				np.save(Save_Loc, Radiosonde_Data)
					
				# Save GPS data
				Save_Loc = self.Storage_Path + self.Processed_Data_Path + 'Radiosonde_Flight_No.' + \
					str(sensor).rjust(2,'0') + '_' + Launch_Datetime.strftime('%Y%m%d') + \
					'/Radiosonde_Flight_PhD_James_No.' + str(sensor) + '_' + Launch_Datetime.strftime('%Y%m%d') + \
					'_' + 'GPSdata.npy'
				np.save(Save_Loc, GPS_Data)
				
			# Append Radiosonde_Data to master array
			Radiosonde_Data_All[str(sensor)] = Radiosonde_Data
			Launch_Datetime_All[str(sensor)] = Launch_Datetime
				
		# return gu.dict2array(Radiosonde_Data_All), gu.dict2array(Launch_Datetime_All)
		return Radiosonde_Data_All, Launch_Datetime_All, Radiosonde_File_All
	
	def _CloudIdentifier(self, Sensor_Package=None):
		"""
		This function will identify the cloud layers within a radiosonde ascent by using the cloud sensor and 
		relative humidity measurements
		
		Notes
		-----
		Layer Type : Classification
			0 = Clear Air, 
			1 = Moist Layer, 
			2 = Cloud Layer.
		
		Returns
		-------
		Cloud_ID : ndarray, dtype = np.int8
			An array with the same size of the input data (e.g. 'height')
			which contains the identifier for each cloud. Starting with
			1, for all height positions where a cloud was identified a 1
			will be used to identify the first cloud for all height 
			positions. Sequentially, the next cloud identified will be
			marked by a 2. N.B. The moist layer clouds are not identified
			within this array.
		Layer_Type : ndarray, dtype = np.int8
			An array with the same size of the input data (e.g. 'height')
			which contains the layer type at each height level (see notes
			for layer type classification). This is very similar to 
			Cloud_ID but does not differentiate between cloud layers.
		
		Reference
		---------
		Zhang, J., H. Chen, Z. Li, X. Fan, L. Peng, Y. Yu, and M. Cribb (2010). Analysis of cloud layer structure 
			in Shouxian, China using RS92 radiosonde aided by 95 GHz cloud radar. J. Geophys. Res., 115, D00K30, 
			doi: 10.1029/2010JD014030.
		WMO, 2017. Clouds. In: Internal Cloud Atlas Manual on the Observation of Clouds and Other Meteors. 
			Hong Kong: WMO, Section 2.2.1.2.
		"""
		
		#Error check that either Radiosonde_File or Sensor_Package has been specified
		if Sensor_Package is None: sys.exit("[Error] You must specify either the Sensor_Package number")
		
		#If not errors then print to console we are running _CloudIdentifier
		if self.verbose is True: gu.cprint("[INFO] You are running _CloudIdentifier from the STABLE release", type='bold')
		
		#Specify the sensors we want to process
		Sensor_Package = np.arange(3,11).astype('S2') if Sensor_Package == 'All' else [Sensor_Package]
		
		Clouds_ID_All = {}
		LayerType_All = {}
		for sensor in Sensor_Package:
			
			#Check the sensor has been processed by _RadiosondeImporter
			try:
				self.Radiosonde_Data[sensor]
			except KeyError:
				if self.verbose is True: print("[Warning] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (sensor))
				continue
				
			############################################################################
			"""[METHOD 1]: Relative Humidity (Zhang et al. 2010)"""
			
			#Define data into new variables
			Z = self.Radiosonde_Data[sensor]['Counts']['height'].copy()
			RH = self.Radiosonde_Data[sensor]['Counts']['RHice'].copy()
			
			#Create Height-Resolving RH Thresholds (see Table 1 in Zhang et al. (2010))
			#N.B. use np.interp(val, RH_Thresholds['altitude'], RH_Thresholds['*RH']) where val is the height range you want the RH Threshold 
			RH_Thresholds = {'minRH' : [0.92, 0.90, 0.88, 0.75, 0.75],
				'maxRH' : [0.95, 0.93, 0.90, 0.80, 0.80],
				'interRH' : [0.84, 0.82, 0.78, 0.70, 0.70],
				'altitude' : [0, 2, 6, 12, 20]}
			
			#Define the cloud height levels as defined by WMO (2017). 
			Z_Levels = {'low' : [0,2], 'middle' : [2,7], 'high' : [5,13]}
			
			#Define the types of layers that can be detected.
			Cloud_Types = {0 : 'Clear Air', 1 : 'Moist (Not Cloud)', 2 : 'Cloud'}
			
			#Define the min, max and interRH for all measure altitudes
			minRH = np.interp(Z, RH_Thresholds['altitude'], RH_Thresholds['minRH'], left=np.nan, right=np.nan)*100
			maxRH = np.interp(Z, RH_Thresholds['altitude'], RH_Thresholds['maxRH'], left=np.nan, right=np.nan)*100
			interRH = np.interp(Z, RH_Thresholds['altitude'], RH_Thresholds['interRH'], left=np.nan, right=np.nan)*100
			
			#[Step 1]: The base of the lowest moist layer is determined as the level when RH exceeds the min-RH corresponding to this level
			minRH_mask = (RH > minRH)
			
			#[Step 2 and 3]: Above the base of the moist layer, contiguous levels with RH over the corresponding min-RH are treated as the same layer
			Z[~minRH_mask] = np.nan
			Clouds_ID = gu.contiguous(Z, 1)
			
			#[Step 4]: Moist layers with bases lower than 120m and thickness's less than 400m are discarded
			for Cloud in np.unique(Clouds_ID)[1:]:
				if Z[Clouds_ID == Cloud][0] < 0.12:
					if Z[Clouds_ID == Cloud][-1] - Z[Clouds_ID == Cloud][0] < 0.4:
						Clouds_ID[Clouds_ID == Cloud] = 0
			
			#[Step 5]: The moist layer is classified as a cloud layer is the maximum RH within this layer is greater than the corresponding max-RH at the base of this moist layer
			LayerType = np.zeros(Z.size, dtype=int) #0: Clear Air, 1: Moist Layer, 2: Cloud Layer
			for Cloud in np.unique(Clouds_ID)[1:]:
				if np.any(RH[Clouds_ID == Cloud] > maxRH[Clouds_ID == Cloud][0]):
					LayerType[Clouds_ID == Cloud] = 2
				else:
					LayerType[Clouds_ID == Cloud] = 1
			
			#[Step 6]: The base of the cloud layers is set to 280m AGL, and cloud layers are discarded if their tops are lower than 280m	
			for Cloud in np.unique(Clouds_ID)[1:]:
				if Z[Clouds_ID == Cloud][-1] < 0.280:
					Clouds_ID[Clouds_ID == Cloud] = 0
					LayerType[Clouds_ID == Cloud] = 0

			#[Step 7]: Two contiguous layers are considered as one-layer cloud if the distance between these two layers is less than 300m or the minimum RH within this distance is more than the maximum inter-RG value within this distance
			for Cloud_Below, Cloud_Above in zip(np.unique(Clouds_ID)[1:-1], np.unique(Clouds_ID)[2:]):
				
				#Define the index between clouds of interest
				Air_Between = np.arange(gu.bool2int(Clouds_ID == Cloud_Below)[-1], gu.bool2int(Clouds_ID == Cloud_Above)[0])
				
				if ((Z[Clouds_ID == Cloud_Above][0] - Z[Clouds_ID == Cloud_Below][-1]) < 0.3) or (np.nanmin(RH[Air_Between]) > np.nanmax(interRH[Air_Between])):
					Joined_Cloud_Mask = np.arange(gu.bool2int(Clouds_ID == Cloud_Below)[0], gu.bool2int(Clouds_ID == Cloud_Above)[-1])
					
					#Update the cloud ID array as the Cloud_Below and Cloud_Above are not distinct clouds
					Clouds_ID[Joined_Cloud_Mask] = Cloud_Below
					
					#Update the LayerType to reflect the new cloud merging
					if np.any(LayerType[Clouds_ID == Cloud_Below] == 2) or np.any(LayerType[Clouds_ID == Cloud_Above] == 2):
						LayerType[Joined_Cloud_Mask] = 2
					else:
						LayerType[Joined_Cloud_Mask] = 1
				
			#[Step 8] Clouds are discarded if their thickness's are less than 30.5m for low clouds and 61m for middle/high clouds
			for Cloud in np.unique(Clouds_ID)[1:]:
				if Z[Clouds_ID == Cloud][0] < Z_Levels['low'][1]:
					if Z[Clouds_ID == Cloud][-1] - Z[Clouds_ID == Cloud][0] < 0.0305:
						Clouds_ID[Clouds_ID == Cloud] = 0
						LayerType[Clouds_ID == Cloud] = 0

				else:
					if Z[Clouds_ID == Cloud][-1] - Z[Clouds_ID == Cloud][0] < 0.0610:
						Clouds_ID[Clouds_ID == Cloud] = 0
						LayerType[Clouds_ID == Cloud] = 0
			
			#Re-update numbering of each cloud identified
			Clouds_ID = gu.contiguous(Clouds_ID, invalid=0)
			
			#Output verbose to screen
			if self.verbose is True:
				print("Detected Clouds and Moist Layers\n--------------------------------")
				for Cloud in np.unique(Clouds_ID)[1:]:
					print("Cloud %s. Cloud Base = %.2fkm, Cloud Top = %.2fkm, Layer Type: %s" % (Cloud, Z[Clouds_ID == Cloud][0], Z[Clouds_ID == Cloud][-1], Cloud_Types[LayerType[Clouds_ID == Cloud][0]]))
			
			#Add data to dictionaries
			Clouds_ID_All[sensor] = Clouds_ID
			LayerType_All[sensor] = LayerType
			
		return Clouds_ID_All, LayerType_All
	
	def _ChargeCalibrator(self, Calibrate=None, Sensor_Package=None, Clouds_ID=None, LayerType=None):

		if self.verbose is True: gu.cprint("[INFO] You are running Radiosonde_ChargeCalibrator from the DEV release", type='bold')

		############################################################################
		"""Prerequisites"""
		
		#Time Controls
		t_begin = time.time()
			
		#Plotting requirements
		import matplotlib.pyplot as plt
		plt.style.use('classic') #necessary if Matplotlib version is >= 2.0.0
		
		#Calibration boundaries
		Height_Boundaries = {0 : [],
			1 : [],
			2 : [],
			3 : [],
			4 : [10.0,12.0],
			5 : [10.5,12.0],
			6 : [],
			7 : [],
			8 : [],
			9 : [6,12.0],
			10 : [12,18.0]}
		
		# Make data local to method
		Radiosonde_File = self.Radiosonde_File[Sensor_Package]
		
		############################################################################
		"""[Step 1] Calibrate bespoke sensors"""
		
		Radiosonde_Data = self.Radiosonde_Data['Units'].copy()
					
		Linear = gu.moving_average(Radiosonde_Data['Lin_Current'], 11)
		Log = gu.moving_average(Radiosonde_Data['Log_Current'], 11)
		
		PosMask = Linear >= 0
		NegMask = Linear < 0
		
		LinearPos = np.log10(Linear[PosMask])
		LogPos = Log[PosMask]
		
		LinearNeg = -np.log10(-Linear[NegMask])
		LogNeg = Log[NegMask]
			
		#Calculate Linear Regressions
		slope_all, intercept_all, r_value_all, p_value_all, std_err_all = sp.stats.linregress(Log, Linear)
		slope_pos, intercept_pos, r_value_pos, p_value_pos, std_err_pos = sp.stats.linregress(LogPos, LinearPos)
		try:
			slope_neg, intercept_neg, r_value_neg, p_value_neg, std_err_neg = sp.stats.linregress(LogNeg, LinearNeg)
		except:
			slope_neg, intercept_neg, r_value_neg, p_value_neg, std_err_neg = (0,0,0,0,0)
		
		if self.verbose is True: print(slope_all, intercept_all, r_value_all, p_value_all, std_err_all)
		if self.verbose is True: print(slope_pos, intercept_pos, r_value_pos, p_value_pos, std_err_pos)
		if self.verbose is True: print(slope_neg, intercept_neg, r_value_neg, p_value_neg, std_err_neg)
		
		############################################################################
		"""[Step 2] Plot the calibration values for positive and negative linear currents"""
		
		plt.clf()
		plt.close()
		
		f, ax = plt.subplots(1,3)
		ax[0].plot(Log, Linear , 'p', ms=1, marker='o', markeredgecolor='None', markerfacecolor='black', alpha=1, label="Clouds")
		ax[1].plot(LogPos, LinearPos , 'p', ms=1, marker='o', markeredgecolor='None', markerfacecolor='black', alpha=1, label="Clouds")
		ax[2].plot(LogNeg, LinearNeg , 'p', ms=1, marker='o', markeredgecolor='None', markerfacecolor='black', alpha=1, label="Clouds")
		
		ax[0].plot(Log, slope_all*Log+intercept_all, lw=0.5, c='red')
		ax[1].plot(LogPos, slope_pos*LogPos+intercept_pos, lw=0.5, c='red')
		ax[2].plot(LogNeg, slope_neg*LogNeg+intercept_neg, lw=0.5, c='red')
		
		ax[0].set_ylabel("Linear Sensor Current (A)", fontsize=8)
		ax[1].set_ylabel("Linear Sensor Current (log10(pA))", fontsize=8)
		ax[2].set_ylabel("Linear Sensor Current (-log10(-pA))", fontsize=8)

		for subplot in ax: subplot.minorticks_on()
		for subplot in ax: subplot.set_xlabel("Log Sensor Current (Counts)", fontsize=8)
		for subplot in ax: subplot.grid(which='major',axis='both',c='grey')
		for subplot in ax: subplot.tick_params(axis='both', which='major', labelsize=8)
		for subplot in ax: subplot.tick_params(axis='both', which='minor', labelsize=8)
		
		f.suptitle("Linear and Log Charge Sensors for Radiosonde Flight No.5", y=0.90)
		
		ax[0].get_xaxis().get_major_formatter().labelOnlyBase = False
		
		for subplot in ax:
			x0, x1 = subplot.get_xlim()
			y0, y1 = subplot.get_ylim()
			subplot.set_aspect(np.abs((x1-x0)/(y1-y0)))
		
		ax[0].annotate("All Data", xy=(0, 1), xycoords='axes fraction', xytext=(20, -20), textcoords='offset pixels', horizontalalignment='left', verticalalignment='top', fontsize=8)
		ax[1].annotate("Positive Linear Current", xy=(0, 1), xycoords='axes fraction', xytext=(20, -20), textcoords='offset pixels', horizontalalignment='left', verticalalignment='top', fontsize=8)
		ax[2].annotate("Negative Linear Current", xy=(0, 1), xycoords='axes fraction', xytext=(20, -20), textcoords='offset pixels', horizontalalignment='left', verticalalignment='top', fontsize=8)
		
		ax[0].annotate("$R^{2}$ = %.4f\n$Counts$ = %.0f" % (r_value_all**2, Log.size), xy=(1, 1), xycoords='axes fraction', fontsize=8, xytext=(-3, -3), textcoords='offset points', ha='right', va='top')
		ax[1].annotate("$R^{2}$ = %.4f\n$Counts$ = %.0f" % (r_value_pos**2, LogPos.size), xy=(1, 1), xycoords='axes fraction', fontsize=8, xytext=(-3, -3), textcoords='offset points', ha='right', va='top')
		ax[2].annotate("$R^{2}$ = %.4f\n$Counts$ = %.0f" % (r_value_neg**2, LogNeg.size), xy=(1, 1), xycoords='axes fraction', fontsize=8, xytext=(-3, -3), textcoords='offset points', ha='right', va='top')
					
		f.set_size_inches(11.7, 4.3)
		
		############################################################################
		"""[Step 3] Save plot to file"""
		
		#Specify the directory the plots are stored in 
		path = os.path.dirname(Radiosonde_File).replace(self.Storage_Path + self.Processed_Data_Path,"")

		#Find any other plots stored in this directory
		previous_plots = glob.glob(self.Storage_Path + self.Radiosonde_Plots_Path + path + "/*")
		
		#Find the biggest 'v' number in plots
		plot_version = []
		for plots in previous_plots:
			try:
				plot_version.append(int(os.path.basename(plots)[34:37]))
			except ValueError:
				plot_version.append(int(os.path.basename(plots)[34:36]))
		
		plot_version = str(np.max(plot_version)+1) if len(plot_version) != 0 else '1'
		
		#Create full directory and file name
		Save_Location = self.Storage_Path + self.Radiosonde_Plots_Path + path + '/' + path + '_v' + plot_version.rjust(2,'0') + '_ChargeCalibrator.png'

		#Ensure the directory exists on file system and save to that location
		gu.ensure_dir(os.path.dirname(Save_Location))
		plt.savefig(Save_Location, bbox_inches='tight', pad_inches=0.1, dpi=300)
		
		#Return regression of positive current, regression of negative current and the boundary for counts
		return (slope_all, intercept_all), (slope_pos, intercept_pos), (slope_neg, intercept_neg), (PosMask, NegMask)
	
	def _CloudHeights(self, sensor, method='Zhang'):
		"""
		Gets the cloud and clear-air heights using either the Zhang or 
		IR method.
		
		Parameters
		----------
		sensor : int or str
			The sensor number of the radiosonde flight.
		method : str, optional, default = 'Zhang'
			The method to compute the cloud and clear-air heights. Options
			are 'Zhang' or 'IR'.
			
		Returns
		-------
		Cloud_Heights : 2D numpy array
			The start and end heights for all clouds detected.
		Clear_Heights : 2D numpy array
			The start and end heights for all clear air detected.
			
		"""
		
		# Quality control args and kwargs.
		sensor = str(sensor)
				
		# Get a copy of the Radiosonde and Clouds_ID data.
		Radiosonde_Data = self.Radiosonde_Data.copy()
		Clouds_ID = self.Clouds_ID[sensor].copy()
		LayerType = self.LayerType.copy()
		
		# Calculate cloud and clear-air heights.
		if method == 'Zhang':
			
			# Get cloud base and cloud top heights for each identified cloud
			Cloud_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clouds_ID == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clouds_ID == Cloud][-1]] for Cloud in np.unique(Clouds_ID)[1:]], dtype=np.float64)

			# Get clear-air base and clear-air top heights from each clear-air region.
			Clear_ID = gu.argcontiguous(LayerType[sensor], valid=0)
			Clear_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][-1]] for Cloud in np.unique(Clear_ID)[1:]], dtype=np.float64)
			
		elif method == 'IR':
			
			# Determine cloud regions from IR data.
			IR = Radiosonde_Data[sensor]['Units']['IR']
			Clouds_ID = gu.contiguous((IR > np.nanpercentile(IR, 80)).astype(int), invalid=0)

			# Determine clear-air regions from IR data.
			Clear_ID = gu.contiguous((IR < np.nanpercentile(IR, 20)).astype(int), invalid=0)
			
			# Get cloud base and cloud top heights for each identified cloud.
			Cloud_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clouds_ID == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clouds_ID == Cloud][-1]] for Cloud in np.unique(Clouds_ID)[1:]], dtype=np.float64)

			# Get clear-air base and clear-air top heights from each clear-air region.
			Clear_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][-1]] for Cloud in np.unique(Clear_ID)[1:]], dtype=np.float64)
							
		else:
			raise ValueError("[_CloudHeights] method parameter can only take the optinos 'Zhang' or 'IR'")
		
		return Cloud_Heights, Clear_Heights
		
	def Superplotter(self):
		"""
		This function will plot the data from a single radiosonde flight
		"""
		
		if self.verbose is True: gu.cprint("[INFO] You are running Superplotter from the DEV release", type='bold')
		
		############################################################################
		"""Prerequisites"""
		
		# Time Controls
		t_begin = time.time()
		
		# Make data local to method
		Radiosonde_File = self.Radiosonde_File[self.sensor_package]
		
		############################################################################
		"""[Step 1] Plot radiosonde data"""

		Title = 'Radiosonde Flight No.' + str(self.sensor_package) + ' (' + self.Launch_Datetime[self.sensor_package].strftime("%d/%m/%Y %H%MUTC") + ')' if self.GPS_File is not None else 'Radiosonde Flight (N/A)'
		if self.sensor_package < 8:
			Superplotter = SPRadiosonde(8, Title, self.height_range, self.Radiosonde_Data[self.sensor_package][self.calibrate], calibrate=self.calibrate) if self.calibrate == "Units" else SPRadiosonde(7, Title, self.height_range, self.Radiosonde_Data[self.sensor_package][self.calibrate], calibrate=self.calibrate)
		else:	
			Superplotter = SPRadiosonde(7, Title, self.height_range, self.Radiosonde_Data[self.sensor_package][self.calibrate], calibrate=self.calibrate)
		
		if self.calibrate in ['Counts', 'Volts']:
			Superplotter.Charge(type='counts')
		else:
			Superplotter.Charge(type='space_charge')
		
		if self.sensor_package < 8:
			Superplotter.Cloud(mask_cyan=(self.Radiosonde_Data[self.sensor_package][self.calibrate]['Parity'] == 1111))
			Superplotter.PLL(type='freq', mask_pll=(self.Radiosonde_Data[self.sensor_package][self.calibrate]['Parity'] == 1112), point=False) if self.sensor_package < 3 else Superplotter.PLL(type='freq', mask_pll=(self.Radiosonde_Data[self.sensor_package][self.calibrate]['Parity'] == 1112), point=True)
			if self.calibrate in ['Units']: Superplotter.PLL(type='slwc', mask_pll=(self.Radiosonde_Data[self.sensor_package][self.calibrate]['Parity'] == 1112), point=False) if self.sensor_package < 3 else Superplotter.PLL(type='slwc', mask_pll=(self.Radiosonde_Data[self.sensor_package][self.calibrate]['Parity'] == 1112), point=True)
		else:
			Superplotter.Cloud()
			Superplotter.Turbulence()
			
		# Plot the processed PLL data
		if (self.calibrate == "units") & (self.sensor_package < 8): Superplotter.ch(14, 'SLWC $(g$ $m^{-3})$', 'Supercooled Liquid\nWater Concentration', check=1112, point=True)
		
		# Plot the cloud boundaries if specified
		if self.Clouds_ID is not None: Superplotter.Cloud_Boundaries(self.Clouds_ID[self.sensor_package], self.LayerType[self.sensor_package], CloudOnly=True)
		
		############################################################################
		"""[Step 2] Save plot and return"""
		
		# Specify the directory the plots are stored in 
		path = os.path.dirname(Radiosonde_File).replace(self.Storage_Path + self.Processed_Data_Path,"")
		
		# Find any other plots stored in this directory
		previous_plots = glob.glob(self.Storage_Path + self.Radiosonde_Plots_Path + path + "/*")
		
		# Find the biggest 'v' number in plots
		plot_version = []
		for plots in previous_plots:
			try:
				plot_version.append(int(os.path.basename(plots)[34:37]))
			except ValueError:
				plot_version.append(int(os.path.basename(plots)[34:36]))
		
		plot_version = str(np.max(plot_version)+1) if len(plot_version) != 0 else '1'
		
		# Create full directory and file name
		Save_Location = self.Storage_Path + self.Radiosonde_Plots_Path + path + '/' + path + '_v' + plot_version.rjust(2,'0') + '_' + str(self.height_range[0]).rjust(2,'0') + 'km_to_' + str(self.height_range[1]).rjust(2,'0') + 'km.png'
		
		# Ensure the directory exists on file system and save to that location
		gu.ensure_dir(os.path.dirname(Save_Location))
		Superplotter.savefig(Save_Location)
		
		if self.verbose is True: print("[INFO] Superplotter completed successfully (In %.2fs)" % (time.time()-t_begin))

	def Tephigram(self, plot_tephigram=False, plot_larkhill=False):
		"""
		The Radiosonde_Tephigram function will plot a tephigram from the dry bulb temperature,
		T_dry and the Dew point Temperature, T_dew for pressure values, P at each corresponding 
		height. 
		
		Certain tephigram outputs are available from this function including:
		1) Lower Condensation Level (LCL) in m
		2) Level of Free Convection (LFC) in m
		3) Environmental Level (EL) in m
		4) Convective Available Potential Energy (CAPE) in J/kg
		5) Convective INhibition (CIN) in J/kg

		Parameters
		----------
		
		plot_tephigram : bool, optional, default is False
			Specify True to plot a tephigram of the sounding data. Otherwise
			just calculate the sounding indices
		plot_larkhill : bool, optional, default is False
			Specify True to add the sounding from Camborne at the closest time
			to the launch time. Only used if plot_tephigram is True.
		
		Outputs
		-------
		
		References
		----------
		Ambaum, M. H. P., 2010. Water in the Atmosphere. In: Thermal Physics of the Atmosphere. Oxford: Wiley & Sons, pp. 93-109
		Marlton, G. 2018. Tephigram. Original Matlab code found in Matlab_Code directory
		Hunt, K. 2018. Tephigram. Original Python code found in the same directory.
		"""
		
		if self.verbose is True: gu.cprint("[INFO] You are running Radiosonde_Tephigram from the STABLE release", type='bold')
			
		############################################################################
		"""Prerequisites"""
		
		# Time Controls
		t_begin = time.time()
		
		# Set-up data importer
		EPCC_Data = EPCC_Importer()
		
		############################################################################
		"""[Step 1] Calibrate bespoke sensors"""
    
		# Return Data (make local to function only. i.e. DON'T use self.Radiosonde_Data)
		Radiosonde_Data = self.Radiosonde_Data[self.sensor_package]['Counts'].copy()
		Radiosonde_File = self.Radiosonde_File[self.sensor_package]
		
		# Extract data into easy to read variables
		Z = Radiosonde_Data['height'][1:]
		Tdry = Radiosonde_Data['Tdry'][1:]
		Tdew = Radiosonde_Data['Tdew'][1:]
		Pres = Radiosonde_Data['P'][1:]
		RH = Radiosonde_Data['RH'][1:]/100; RH -= np.max(RH) - 0.01
		Wind_Mag = (Radiosonde_Data['u'][1:]**2 + Radiosonde_Data['v'][1:]**2)**0.5
		Wind_Dir = np.arctan2(Radiosonde_Data['u'][1:], Radiosonde_Data['v'][1:]) * 180 / np.pi
			
		############################################################################
		"""[Step 2] Create Tephigram"""
		
		if plot_tephigram is True:
		
			if self.verbose is True: print("[INFO] Plotting Tephigram...")
			print("plot_larkhill", plot_larkhill)
			# Unpack variables
			Z_Plot = Radiosonde_Data['height']
			Tdry_Plot = Radiosonde_Data['Tdry']
			Tdew_Plot = Radiosonde_Data['Tdew']
			Pres_Plot = Radiosonde_Data['P']
			
			# Subset the tephigram to specified location
			locator = gu.argneararray(Z_Plot, np.array(self.height_range)*1000)
			anchor = np.array([(Pres_Plot[locator]),(Tdry_Plot[locator])]).T
			
			Pres_Plot_Antinan, Tdry_Plot_Antinan, Tdew_Plot_Antinan = gu.antinan(np.array([Pres_Plot, Tdry_Plot, Tdew_Plot]), unpack=True)
			
			# Group the dews, temps and wind profile measurements
			dews = zip(Pres_Plot_Antinan, Tdew_Plot_Antinan)
			temps = zip(Pres_Plot_Antinan, Tdry_Plot_Antinan)
			barb_vals = zip(Pres,Wind_Dir,Pres_Plot)
					
			# Create Tephigram plot
			Tephigram = SPTephigram()
			
			# Plot Reading sounding data
			profile_t1 = Tephigram.plot(temps, color="red", linewidth=1, label='Reading Dry Bulb Temperature', zorder=5)
			profile_d1 = Tephigram.plot(dews, color="blue", linewidth=1, label='Reading Dew Bulb Temperature', zorder=5)
					
			# Plot Larkhill sounding data
			if plot_larkhill is True:
				
				# Determine ULS data
				ULS_File = sorted(glob.glob(PhD_Global.Raw_Data_Path + 'Met_Data/ULS/03743/*'))
				
				# Check any files were found
				if len(ULS_File) > 0:
					
					ULS_Date = np.zeros(len(ULS_File), dtype=object)
					for i, file in enumerate(ULS_File):
						try:
							ULS_Date[i] = datetime.strptime(os.path.basename(file), '%Y%m%d_%H_03743_UoW_ULS.csv')
						except:
							ULS_Date[i] = datetime(1900,1,1)
					
					# Find Nearest Upper Level Sounding Flight to Radiosonde Flight
					ID = gu.argnear(ULS_Date, self.Launch_Datetime[self.sensor_package])
					
					# Check the amount of time between Reading and Larkhill
					# soundings does not exceed 24 hrs.
					if np.abs(self.Launch_Datetime[self.sensor_package] - ULS_Date[ID]).seconds < 86400:
					
						print("[INFO] Radiosonde Launch Time:", self.Launch_Datetime[self.sensor_package], "Larkhill Launch Time:", ULS_Date[ID])
						
						# Import Larkhill Radiosonde Data
						press_larkhill, temps_larkhill, dews_larkhill = EPCC_Data.ULS_Calibrate(ULS_File[ID], unpack=True, PRES=True, TEMP=True, DWPT=True)
						
						# Match Larkhill pressures with Reading pressures
						mask = [gu.argnear(press_larkhill, Pres_Plot[0]), gu.argnear(press_larkhill, Pres_Plot[-1])]
						press_larkhill = press_larkhill[mask[0]:mask[1]]
						temps_larkhill = temps_larkhill[mask[0]:mask[1]]
						dews_larkhill = dews_larkhill[mask[0]:mask[1]]
							
						dews_larkhill = zip(press_larkhill, dews_larkhill)
						temps_larkhill = zip(press_larkhill, temps_larkhill)
						
						# Plot Larkhill sounding data
						profile_t1 = Tephigram.plot(temps_larkhill, color="red", linestyle=':', linewidth=1, label='Larkhill Dry Bulb Temperature', zorder=5)
						profile_d1 = Tephigram.plot(dews_larkhill, color="blue", linestyle=':', linewidth=1, label='Larkhill Dew Bulb Temperature', zorder=5)
					
					else:
						#warnings.warn("[WARNING] No Larkhill (03743) sounding data was found within 24hrs of the ascent!", ImportWarning)
						gu.cprint("[WARNING] No Larkhill (03743) sounding data was found within 24hrs of the ascent!", type='warning')
				else:
					#warnings.warn("[WARNING] No Larkhill (03743) sounding data was found!", ImportWarning)
					gu.cprint("[WARNING] No Larkhill (03743) sounding data was found!", type='warning')
				
			# Add extra information to Tephigram plot
			# Tephigram.axes.set(title=Title, xlabel="Potential Temperature $(^\circ C)$", ylabel="Dry Bulb Temperature $(^\circ C)$")
			Title = 'Radiosonde Tephigram Flight No.' + str(self.sensor_package) + ' (' + self.Launch_Datetime[self.sensor_package].strftime("%d/%m/%Y %H%MUTC") + ')' if self.GPS_File is not None else 'Radiosonde Tephigram Flight (N/A)'
			Tephigram.axes.set(title=Title)
					
			# [OPTIONAL] Add wind profile information to Tephigram.
			# profile_t1.barbs(barb_vals)
			
			############################################################################
			"""Save plot to file"""

			# Specify the directory the plots are stored in 
			path = os.path.dirname(Radiosonde_File).replace(self.Storage_Path + self.Processed_Data_Path,"")
			
			# Find any other plots stored in this directory
			previous_plots = glob.glob(self.Storage_Path + self.Tephigram_Plots_Path + path + "/*")
			
			# Find the biggest 'v' number in plots
			plot_version = []
			for plots in previous_plots:
				try:
					plot_version.append(int(os.path.basename(plots)[34:37]))
				except ValueError:
					plot_version.append(int(os.path.basename(plots)[34:36]))
			
			plot_version = str(np.max(plot_version)+1) if len(plot_version) != 0 else '1'
			
			# Create full directory and file name
			Save_Location = self.Storage_Path + self.Tephigram_Plots_Path + path + '/' + path + '_v' + plot_version.rjust(2,'0') + '_' + str(self.height_range[0]).rjust(2,'0') + 'km_to_' + str(self.height_range[1]).rjust(2,'0') + 'km.png'
			
			# Ensure the directory exists on file system and save to that location
			gu.ensure_dir(os.path.dirname(Save_Location))
			
			print("Save_Location", Save_Location)
			Tephigram.savefig(Save_Location)      

		############################################################################
		"""[Step 3] Calculate Stability Indices"""
		
		print("[INFO] Calculating Stability Indices...")
		
		# Common Pressure Levels
		P_500 = gu.argnear(Pres, 500)
		P_700 = gu.argnear(Pres, 700)
		P_850 = gu.argnear(Pres, 850)
		
		# Showalter stability index
		#S = Tdry[P_500] - Tl
		
		# K-Index
		K = (Tdry[P_850] - Tdry[P_500]) + Tdew[P_850] - (Tdry[P_700] - Tdew[P_700])
		
		# Cross Totals Index
		CT = Tdew[P_850] - Tdry[P_500]
		
		# Vertical Totals Index
		VT = Tdry[P_850] - Tdry[P_500]
		
		# Total Totals Index
		TT = VT + CT
		
		# SWEAT Index
		ms2kn = 1.94384	# Conversion between m/s to knots
			
		SW_1 = 20*(TT-49)
		SW_2 = 12*Tdew[P_850]
		SW_3 = 2*Wind_Mag[P_850]*ms2kn
		SW_4 = Wind_Mag[P_500]*ms2kn
		SW_5 = 125*(np.sin(Wind_Dir[P_500]-Wind_Dir[P_850]) + 0.2)
		
		# Condition SWEAT Term 1 from several conditions
		SW_1 = 0 if SW_1 < 49 else SW_1

		# Condition SWEAT Term 5 with several conditions
		if (Wind_Dir[P_850] > 130) & (Wind_Dir[P_850] < 250):
			if (Wind_Dir[P_500] > 210) & (Wind_Dir[P_500] < 310):
				if Wind_Dir[P_500]-Wind_Dir[P_850] > 0:
					if (Wind_Mag[P_500]*ms2kn > 15) & (Wind_Mag[P_850]*ms2kn > 15):
						SW_5 = SW_5
					else:
						SW_5 = 0
				else:
					SW_5 = 0
			else:
				SW_5 = 0
		else:
			SW_5 = 0
		
		# Calulate Final Product
		SW = SW_1 + SW_2 + SW_3 + SW_4 + SW_5
		
		print("Stability Indices")
		print("-----------------")
		print("K-Index:", K)
		print("Cross Totals Index:", CT)
		print("Vettical Totals Index:", VT)
		print("Total Totals Index:", TT)
		print("SWEAT Index:", SW)
		print("\n")
		
		############################################################################
		"""[Step 4] Calculate Tephigram Indices"""
		
		# Convert Temperature back to Kelvin
		Tdry += 273.15
		Tdew += 273.15
				
		# Convert Height into metres
		Z *= 1000
				
		print("Tdry", Tdry, Tdry.shape)
		print("Tdew", Tdew, Tdew.shape)
		print("Z", Z, Z.shape)
		
		
		# Constants
		over27 = 0.286 # Value used for calculating potential temperature 2/7
		L = 2.5e6  #Latent evaporation 2.5x10^6
		epsilon = 0.622
		E = 6.014  #e in hpa 
		Rd = 287 #R constant for dry air
		
		# Equations
		es = lambda T: 6.112*np.exp((17.67*(T-273.15))/(T-29.65)) #Teten's Formula for Saturated Vapour Pressure converted for the units of T in Kelvin rather than Centigrade
		
		# Calculate Theta and Theta Dew
		theta = Tdry*(1000/Pres)**over27
		thetadew = Tdew*(1000/Pres)**over27
			
		# Find the Lifting Condensation Level (LCL)
		qs_base = 0.622*es(Tdew[0])/Pres[0]
		
		theta_base = theta[0]
		Pqs_base = 0.622*es(Tdry)/qs_base  #Calculate a pressure for constant qs
		Pqs_base = Tdry*(1000/Pqs_base)**(2/7) #Calculates pressure in term of P temp
		
		# print("Tdew[0]", Tdew[0])
		# print("Pres[0]", Pres[0])
		# print("qs_base",qs_base)
		# print("theta_base", theta_base)
		# print("Pqs_base", Pqs_base)
		
		# Find first location where Pqs_base > theta_base
		y1 = np.arange(Pqs_base.size)[Pqs_base > theta_base][0]
		# print(Pqs_base[y1])
		# print(y1)
		# print(gu.argnear(Pqs_base, theta_base))
		
		LCL = Z[y1]
			
		Tarr = np.zeros(Tdry.size)
		thetaarr = np.zeros(Tdry.size)

		T_temp = Tdry[y1]
		P_temp = 1000*(T_temp/Pqs_base[y1])**3.5
		qs0 = 0.622*es(T_temp)/P_temp
		
		thetaarr[y1] = Pqs_base[y1]
		Tarr[y1] = T_temp
		
		for i in xrange(y1+1, y1+100):
			T_temp -= 1
			P_temp = 1000*(T_temp/thetaarr[i-1])**3.5
			qs = 0.622*es(T_temp)/P_temp
			thetaarr[i] = thetaarr[i-1] - ((2.5E6/1004)*(thetaarr[i-1]/T_temp) * (qs-qs0))
			qs0 = qs
			Tarr[i] = T_temp
			
		# Now need to integrate back to 1000hpa
		T_temp = Tdry[y1]
		P_temp = 1000*(T_temp/Pqs_base[y1])**3.5
		qs0 = 0.622*es(T_temp)/P_temp
		thetaarr[y1] = Pqs_base[y1]
		Tarr[y1] = T_temp
		for i in xrange(y1-1):
			T_temp += 1
			P_temp = 1000*(T_temp/thetaarr[(y1-i)+1])**3.5
			qs = 0.622*es(T_temp)/P_temp
			thetaarr[y1-i] = thetaarr[(y1-i)+1] - ((2.5E6/1004)*(thetaarr[(y1-i)+1]/T_temp) * (qs-qs0))
			qs0 = qs
			Tarr[y1-i] = T_temp
		
		y8 = (thetaarr>253) & (thetaarr<380)
		thetaarr = thetaarr[y8]
		Tarr = Tarr[y8]
		
		# Now find environmental levels and LFC begin by converting thetaarr into P
		Pthetaeq = 1000/(thetaarr/Tarr)**3.5
		l5 = np.isnan(Pthetaeq)
		Pthetaeq[l5] = []
		
		# Now interpolate on to rs height co-ordinates	
		TEMP = sp.interpolate.interp1d(Pthetaeq,[thetaarr,Tarr], fill_value="extrapolate")(Pres)
		thetaarr = TEMP[0]
		Tarr = TEMP[1]

		del(TEMP)
		
		
		
		y5 = np.arange(Tdry.size)[Tdry < Tarr]
		
		print("y5", y5)
		
		if np.any(y5):
			LFC = Z[y5[0]]
			EL = Z[y5[-1]]
			
			# Finds CIN area above LCL
			y6 = np.arange(Tdry.size)[(Z < LFC) & (Z >= LCL) & (Tdry > Tarr)]
			y7 = np.arange(Tdry.size)[(Z < LCL) & (Tdry > Tarr)]
			
			Pstart = Pres[y5[-1]]
			
			# Now need to calculate y5 temperatures into virtual temperatures
			Tvdash = Tarr/(1-(E/Pres)*(1-epsilon))
			Tv = Tdry/(1-(E/Pres)*(1-epsilon))
			T_adiabat = ((theta_base/(1000/Pres)**over27))
			Tv_adiabat = T_adiabat/(1-(E/Pres)*(1-epsilon))
			
			# Now need to calculate CAPE... and CIN to use CAPE = R_d = intergral(LFC,EL)(T'_v - T_v) d ln p
			CAPE = 0
			for i in xrange(y5[-2], y5[0], -1):
				CAPE += (Rd*(Tvdash[i] - Tv[i]) * np.log(Pres[i]/Pres[i+1]));
			
			# Now we use same technique to calculate CIN
			CIN=0;
			if len(y6) != 0:
				for i in xrange(y6[-2], y6[0], -1):
					CIN += (Rd*(Tvdash[i] - Tv[i]) * np.log(Pres[i]/Pres[i+1]))
		
			# Now calculate temperature along the dry adiabat
			y7 = np.arange(Tdry.size)[(Z < LCL) & (Tv > Tv_adiabat)]
			if len(y7) != 0:
				for i in xrange(y7[-2], y7[0], -1): 
					CIN += (Rd*(Tv_adiabat[i] - Tv[i]) * np.log(Pres[i]/Pres[i+1]));   
			
		else:
			LFC = np.nan
			EL = np.nan
			CAPE = 0
			CIN = 0
		
		# Print out information
		print("Parcel Information")
		print("------------------")
		print("LCL = %.2fm" % LCL)
		print("LFC = %.2fm" % LFC)
		print("EL = %.2fm" % EL)
		print("CAPE %.2f J/kg" % CAPE)
		print("CIN %.2f J/kg" % CIN)
		print("\n")
		
		print("[INFO] Radiosonde_Tephigram has been completed successfully (In %.2fs)" % (time.time()-t_begin))
		
		return LCL, LFC, EL, CAPE, CIN		
	
	def Hypothesis1(self):
		"""
		HYPOTHESIS 1: Convective clouds containing an ice phase and 
		a high relative humidity with respects to ice will contain more 
		charge.
		"""
		
		if self.verbose is True: gu.cprint("[INFO] You are running Hypothesis1 from the DEV release", type='bold')
		
		############################################################################
		"""Prerequisites"""
		
		# Time Controls
		t_begin = time.time()
		
		# Radiosonde Data
		Radiosonde_Data = self.Radiosonde_Data.copy()
		Clouds_ID = self.Clouds_ID.copy()
		LayerType = self.LayerType.copy()

		# Set-up data importer
		EPCC_Data = EPCC_Importer()
		
		# Set-up plotting
		gu.backend_changer()
		
		# Conditionals
		section1 = False
		plot_spacecharge	= True
		plot_ir				= True
		plot_cyan			= True
		plot_ircyan			= True
		
		section2 = True
		
		############################################################################
		
		# Arrays
		Cloud_Type = []
		Cloud_SpaceCharge = [] 
		Cloud_IR = []
		Cloud_Cyan = [] 
		Cloud_IRdiffCyan = []
		Air_Type = []
		Air_SpaceCharge = []
		Air_IR = []
		Air_Cyan = [] 
		Air_IRdiffCyan = []
		
		Cloud_SpaceCharge_Liquid = []
		Cloud_IR_Liquid = []
		Cloud_Cyan_Liquid = []
		Cloud_IRdiffCyan_Liquid = []
		Cloud_RH_Liquid = []
		
		Cloud_SpaceCharge_Ice = []
		Cloud_IR_Ice = []
		Cloud_Cyan_Ice = []
		Cloud_IRdiffCyan_Ice = []
		Cloud_RH_Ice = []
		
		Cloud_SpaceCharge_Mixed = []
		Cloud_IR_Mixed = []
		Cloud_Cyan_Mixed = []
		Cloud_IRdiffCyan_Mixed = []
		Cloud_RH_Mixed = []
		
		Air_SpaceCharge_Liquid = []
		Air_IR_Liquid = []
		Air_Cyan_Liquid = []
		Air_IRdiffCyan_Liquid = []
		Air_RH_Liquid = []
		
		Air_SpaceCharge_Ice = []
		Air_IR_Ice = []
		Air_Cyan_Ice = []
		Air_IRdiffCyan_Ice = []
		Air_RH_Ice = []
		
		Air_SpaceCharge_Mixed = []
		Air_IR_Mixed = []
		Air_Cyan_Mixed = []
		Air_IRdiffCyan_Mixed = []
		Air_RH_Mixed = []
		
		Sensor_Package = np.arange(3,11).astype('S2')
		#Sensor_Package = ['4']
		for sensor in Sensor_Package:
			
			# Check the sensor has been processed by _RadiosondeImporter
			try:
				Radiosonde_Data[sensor]
			except KeyError:
				if self.verbose is True: print("[Warning] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (sensor))
				continue
			
			############################################################################
			# Get cloud base and cloud top heights for each identified cloud
			
			Cloud_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][-1]] for Cloud in np.unique(Clouds_ID[sensor])[1:]], dtype=np.float64)
			
			Clear_Heights = [[0,Cloud_Heights[0,0]]]
			for i in xrange(Cloud_Heights.shape[0]-1):
				Clear_Heights.append([Cloud_Heights[i,1], Cloud_Heights[i+1,0]])
			Clear_Heights.append([Cloud_Heights[-1,1], self.height_range[1]])
			Clear_Heights = np.array(Clear_Heights)
			
			############################################################################
			
			# Remove nan's from data
			Time, Height, Tdry, RH, SpaceCharge, IR, Cyan, IRdiffCyan = gu.antifinite((Radiosonde_Data[sensor]['Units']['time'], 
				Radiosonde_Data[sensor]['Units']['height'],
				Radiosonde_Data[sensor]['Units']['Tdry'],
				Radiosonde_Data[sensor]['Units']['RHice'],
				np.abs(Radiosonde_Data[sensor]['Units']['SpaceCharge']),
				Radiosonde_Data[sensor]['Units']['IR'],
				Radiosonde_Data[sensor]['Units']['Cyan'],
				Radiosonde_Data[sensor]['Units']['IR'] - Radiosonde_Data[sensor]['Units']['Cyan']), 
				unpack=True)

			for cloud in Cloud_Heights:
			
				# Get index of lowest cloud
				CloudIndex = gu.searchsorted(Height, cloud)
			
				# Subset data
				Tdry_Subset = Tdry[CloudIndex[0]:CloudIndex[1]]
				RH_Subset = RH[CloudIndex[0]:CloudIndex[1]]
				SpaceCharge_Subset = SpaceCharge[CloudIndex[0]:CloudIndex[1]]
				IR_Subset = IR[CloudIndex[0]:CloudIndex[1]]
				Cyan_Subset = Cyan[CloudIndex[0]:CloudIndex[1]]
				IRdiffCyan_Subset = IRdiffCyan[CloudIndex[0]:CloudIndex[1]]
				
				# Test whether cloud is a liquid, mixed or ice phase
				if np.all(Tdry_Subset > 0):
					Cloud_Type.append("Liquid")
					Cloud_SpaceCharge_Liquid.append(SpaceCharge_Subset/1000)
					Cloud_IR_Liquid.append(IR_Subset)
					Cloud_Cyan_Liquid.append(Cyan_Subset)
					Cloud_IRdiffCyan_Liquid.append(IRdiffCyan_Subset)
					Cloud_RH_Liquid.append(RH_Subset)
				elif np.all(Tdry_Subset < 0):
					Cloud_Type.append("Ice")
					Cloud_SpaceCharge_Ice.append(SpaceCharge_Subset/1000)
					Cloud_IR_Ice.append(IR_Subset)
					Cloud_Cyan_Ice.append(Cyan_Subset)
					Cloud_IRdiffCyan_Ice.append(IRdiffCyan_Subset)
					Cloud_RH_Ice.append(RH_Subset)
				else:
					Cloud_Type.append("Mixed")
					Cloud_SpaceCharge_Mixed.append(SpaceCharge_Subset/1000)
					Cloud_IR_Mixed.append(IR_Subset)
					Cloud_Cyan_Mixed.append(Cyan_Subset)
					Cloud_IRdiffCyan_Mixed.append(IRdiffCyan_Subset)
					Cloud_RH_Mixed.append(RH_Subset)
					
				Cloud_SpaceCharge.append(np.nanpercentile(SpaceCharge_Subset, 95))
				Cloud_IR.append(np.nanpercentile(IR_Subset, 95))
				Cloud_Cyan.append(np.nanpercentile(Cyan_Subset, 95))
				Cloud_IRdiffCyan.append(np.nanpercentile(IRdiffCyan_Subset, 95))

			for air in Clear_Heights:
			
				# Get index of lowest air
				AirIndex = gu.searchsorted(Height, air)
			
				# Subset data
				Tdry_Subset = Tdry[AirIndex[0]:AirIndex[1]]
				RH_Subset = RH[AirIndex[0]:AirIndex[1]]
				SpaceCharge_Subset = SpaceCharge[AirIndex[0]:AirIndex[1]]
				IR_Subset = IR[AirIndex[0]:AirIndex[1]]
				Cyan_Subset = Cyan[AirIndex[0]:AirIndex[1]]
				IRdiffCyan_Subset = IRdiffCyan[AirIndex[0]:AirIndex[1]]
				
				#Test whether air is a liquid, mixed or ice phase
				if np.all(Tdry_Subset > 0):
					Air_Type.append("Liquid")
					Air_SpaceCharge_Liquid.append(SpaceCharge_Subset/1000)
					Air_IR_Liquid.append(IR_Subset)
					Air_Cyan_Liquid.append(Cyan_Subset)
					Air_IRdiffCyan_Liquid.append(IRdiffCyan_Subset)
					Air_RH_Liquid.append(RH_Subset)
				elif np.all(Tdry_Subset < 0):
					Air_Type.append("Ice")
					Air_SpaceCharge_Ice.append(SpaceCharge_Subset/1000)
					Air_IR_Ice.append(IR_Subset)
					Air_Cyan_Ice.append(Cyan_Subset)
					Air_IRdiffCyan_Ice.append(IRdiffCyan_Subset)
					Air_RH_Ice.append(RH_Subset)
				else:
					Air_Type.append("Mixed")
					Air_SpaceCharge_Mixed.append(IR_Subset/1000)
					Air_IR_Mixed.append(SpaceCharge_Subset)
					Air_Cyan_Mixed.append(Cyan_Subset)
					Air_IRdiffCyan_Mixed.append(IRdiffCyan_Subset)
					Air_RH_Mixed.append(RH_Subset)
				
				Air_SpaceCharge.append(np.nanpercentile(SpaceCharge_Subset, 95))
				Air_IR.append(np.nanpercentile(IR_Subset, 95))
				Air_Cyan.append(np.nanpercentile(Cyan_Subset, 95))
				Air_IRdiffCyan.append(np.nanpercentile(IRdiffCyan_Subset, 95))
		
		#Flatten arrays
		Cloud_SpaceCharge_Liquid = gu.flatten(Cloud_SpaceCharge_Liquid, type='ndarray', dtype=np.float64)
		Cloud_SpaceCharge_Ice = gu.flatten(Cloud_SpaceCharge_Ice, type='ndarray', dtype=np.float64)
		Cloud_SpaceCharge_Mixed = gu.flatten(Cloud_SpaceCharge_Mixed, type='ndarray', dtype=np.float64)
		Cloud_IR_Liquid = gu.flatten(Cloud_IR_Liquid, type='ndarray', dtype=np.float64)
		Cloud_IR_Ice = gu.flatten(Cloud_IR_Ice, type='ndarray', dtype=np.float64)
		Cloud_IR_Mixed = gu.flatten(Cloud_IR_Mixed, type='ndarray', dtype=np.float64)
		Cloud_Cyan_Liquid = gu.flatten(Cloud_Cyan_Liquid, type='ndarray', dtype=np.float64)
		Cloud_Cyan_Ice = gu.flatten(Cloud_Cyan_Ice, type='ndarray', dtype=np.float64)
		Cloud_Cyan_Mixed = gu.flatten(Cloud_Cyan_Mixed, type='ndarray', dtype=np.float64)
		Cloud_IRdiffCyan_Liquid = gu.flatten(Cloud_IRdiffCyan_Liquid, type='ndarray', dtype=np.float64)
		Cloud_IRdiffCyan_Ice = gu.flatten(Cloud_IRdiffCyan_Ice, type='ndarray', dtype=np.float64)
		Cloud_IRdiffCyan_Mixed = gu.flatten(Cloud_IRdiffCyan_Mixed, type='ndarray', dtype=np.float64)
		Cloud_RH_Liquid = gu.flatten(Cloud_RH_Liquid, type='ndarray', dtype=np.float64)
		Cloud_RH_Ice = gu.flatten(Cloud_RH_Ice, type='ndarray', dtype=np.float64)
		Cloud_RH_Mixed = gu.flatten(Cloud_RH_Mixed, type='ndarray', dtype=np.float64)
		
		Air_SpaceCharge_Liquid = gu.flatten(Air_SpaceCharge_Liquid, type='ndarray', dtype=np.float64)
		Air_SpaceCharge_Ice = gu.flatten(Air_SpaceCharge_Ice, type='ndarray', dtype=np.float64)
		Air_SpaceCharge_Mixed = gu.flatten(Air_SpaceCharge_Mixed, type='ndarray', dtype=np.float64)
		Air_IR_Liquid = gu.flatten(Air_IR_Liquid, type='ndarray', dtype=np.float64)
		Air_IR_Ice = gu.flatten(Air_IR_Ice, type='ndarray', dtype=np.float64)
		Air_IR_Mixed = gu.flatten(Air_IR_Mixed, type='ndarray', dtype=np.float64)
		Air_Cyan_Liquid = gu.flatten(Air_Cyan_Liquid, type='ndarray', dtype=np.float64)
		Air_Cyan_Ice = gu.flatten(Air_Cyan_Ice, type='ndarray', dtype=np.float64)
		Air_Cyan_Mixed = gu.flatten(Air_Cyan_Mixed, type='ndarray', dtype=np.float64)
		Air_IRdiffCyan_Liquid = gu.flatten(Air_IRdiffCyan_Liquid, type='ndarray', dtype=np.float64)
		Air_IRdiffCyan_Ice = gu.flatten(Air_IRdiffCyan_Ice, type='ndarray', dtype=np.float64)
		Air_IRdiffCyan_Mixed = gu.flatten(Air_IRdiffCyan_Mixed, type='ndarray', dtype=np.float64)
		Air_RH_Liquid = gu.flatten(Air_RH_Liquid, type='ndarray', dtype=np.float64)
		Air_RH_Ice = gu.flatten(Air_RH_Ice, type='ndarray', dtype=np.float64)
		Air_RH_Mixed = gu.flatten(Air_RH_Mixed, type='ndarray', dtype=np.float64)
		
		if section1 is True:
			"""Plots the back-to-back histograms of the space charge, IR and cyan for
			liquid, mixed and ice clouds"""
						
			if plot_spacecharge is True:
				############################################################################
				"""Space Charge"""
				
				print("Mann-Whitney U-Test", sp.stats.mannwhitneyu(Cloud_IRdiffCyan_Liquid, Cloud_IRdiffCyan_Ice, alternative='two-sided'))
				print("Wilcoxon signed-rank test", sp.stats.wilcoxon(Cloud_IRdiffCyan_Liquid, np.random.choice(Cloud_IRdiffCyan_Ice, Cloud_IRdiffCyan_Liquid.size)))
				
				# Plot Parameters
				data = [[Cloud_SpaceCharge_Liquid, Cloud_SpaceCharge_Mixed],
						[Cloud_SpaceCharge_Liquid, Cloud_SpaceCharge_Ice],
						[Cloud_SpaceCharge_Mixed, Cloud_SpaceCharge_Ice]]
				ylabel = [["Space Charge (nC m$^{-3}$)", "Space Charge (nC m$^{-3}$)"],
						  ["Space Charge (nC m$^{-3}$)", "Space Charge (nC m$^{-3}$)"],
						  ["Space Charge (nC m$^{-3}$)", "Space Charge (nC m$^{-3}$)"]]
				annotate = [["Liquid Clouds", "Mixed Clouds"],
							["Liquid Clouds", "Ice Clouds"],
							["Mixed Clouds", "Ice Clouds"]]
				name = [["Liquid", "Mixed"],
						["Liquid", "Ice"],
						["Mixed", "Ice"]]
				bins = [[20,20],
						[20,20],
						[20,20]]
				ylim = [[[0,20],[0,20]],
						[[0,20],[0,20]],
						[[0,20],[0,20]]]
				xscale = [['log', 'log'],
						  ['log', 'log'],
						  ['log', 'log']]
				yscale = [['linear', 'linear'],
						  ['linear', 'linear'],
						  ['linear', 'linear']]
				filename = self.Storage_Path + 'Plots/Hypothesis_1/SpaceCharge_AllPhasesClouds_Histogram.png'
				
				# Call Back2Back_Histogram with plot parameters
				Back2Back_Histogram(
					data, 
					filename,
					bins,
					ylabel,
					annotate,
					ylim,
					xscale,
					yscale)
			
			if plot_ir is True:
				############################################################################
				"""IR"""
				
				data = [[Cloud_IR_Liquid, Cloud_IR_Mixed],
						[Cloud_IR_Liquid, Cloud_IR_Ice],
						[Cloud_IR_Mixed, Cloud_IR_Ice]]
				ylabel = [["IR Cloud Sensor (V)", "IR Cloud Sensor (V)"],
						  ["IR Cloud Sensor (V)", "IR Cloud Sensor (V)"],
						  ["IR Cloud Sensor (V)", "IR Cloud Sensor (V)"]]
				annotate = [["Liquid Clouds", "Mixed Clouds"],
							["Liquid Clouds", "Ice Clouds"],
							["Mixed Clouds", "Ice Clouds"]]
				name = [["Liquid", "Mixed"],
						["Liquid", "Ice"],
						["Mixed", "Ice"]]
				bins = [[20,20],
						[20,20],
						[20,20]]
				ylim = [[[0,0.06],[0,0.06]],
						[[0,0.06],[0,0.06]],
						[[0,0.06],[0,0.06]]]
				xscale = [['log', 'log'],
						  ['log', 'log'],
						  ['log', 'log']]
				yscale = [['linear', 'linear'],
						  ['linear', 'linear'],
						  ['linear', 'linear']]
				filename = self.Storage_Path + 'Plots/Hypothesis_1/IR_AllPhasesClouds_Histogram.png'
				
				# Call Back2Back_Histogram with plot parameters
				Back2Back_Histogram(
					data, 
					filename,
					bins,
					ylabel,
					annotate,
					ylim,
					xscale,
					yscale)
			
			if plot_cyan is true:
				############################################################################
				"""Cyan"""		
					
				data = [[Cloud_Cyan_Liquid, Cloud_Cyan_Mixed],
						[Cloud_Cyan_Liquid, Cloud_Cyan_Ice],
						[Cloud_Cyan_Mixed, Cloud_Cyan_Ice]]
				ylabel = [["Cyan Cloud Sensor (V)", "Cyan Cloud Sensor (V)"],
						  ["Cyan Cloud Sensor (V)", "Cyan Cloud Sensor (V)"],
						  ["Cyan Cloud Sensor (V)", "Cyan Cloud Sensor (V)"]]
				annotate = [["Liquid Clouds", "Mixed Clouds"],
							["Liquid Clouds", "Ice Clouds"],
							["Mixed Clouds", "Ice Clouds"]]
				name = [["Liquid", "Mixed"],
						["Liquid", "Ice"],
						["Mixed", "Ice"]]
				bins = [[20,20],
						[20,20],
						[20,20]]
				ylim = [[[0,0.06],[0,0.06]],
						[[0,0.06],[0,0.06]],
						[[0,0.06],[0,0.06]]]
				xscale = [['log', 'log'],
						  ['log', 'log'],
						  ['log', 'log']]
				yscale = [['linear', 'linear'],
						  ['linear', 'linear'],
						  ['linear', 'linear']]
				filename = self.Storage_Path + 'Plots/Hypothesis_1/Cyan_AllPhasesClouds_Histogram.png'
				
				# Call Back2Back_Histogram with plot parameters
				Back2Back_Histogram(
					data, 
					filename,
					bins,
					ylabel,
					annotate,
					ylim,
					xscale,
					yscale)
			
			if plot_ircyan is True:
				############################################################################
				"""IR - Cyan"""
				
				data = [[Cloud_IRdiffCyan_Liquid, Cloud_IRdiffCyan_Mixed],
						[Cloud_IRdiffCyan_Liquid, Cloud_IRdiffCyan_Ice],
						[Cloud_IRdiffCyan_Mixed, Cloud_IRdiffCyan_Ice]]
				ylabel = [["IR - Cyan Cloud Sensor (V)", "IR - Cyan Cloud Sensor (V)"],
						  ["IR - Cyan Cloud Sensor (V)", "IR - Cyan Cloud Sensor (V)"],
						  ["IR - Cyan Cloud Sensor (V)", "IR - Cyan Cloud Sensor (V)"]]
				annotate = [["Liquid Clouds", "Mixed Clouds"],
							["Liquid Clouds", "Ice Clouds"],
							["Mixed Clouds", "Ice Clouds"]]
				name = [["Liquid", "Mixed"],
						["Liquid", "Ice"],
						["Mixed", "Ice"]]
				bins = [[20,20],
						[20,20],
						[20,20]]
				ylim = [[[-0.1,0.1],[-0.1,0.1]],
						[[-0.1,0.1],[-0.1,0.1]],
						[[-0.1,0.1],[-0.1,0.1]]]
				xscale = [['log', 'log'],
						  ['log', 'log'],
						  ['log', 'log']]
				yscale = [['linear', 'linear'],
						  ['linear', 'linear'],
						  ['linear', 'linear']]
				filename = self.Storage_Path + 'Plots/Hypothesis_1/IRdiffCyan_AllPhasesClouds_Histogram.png'
				
				# Call Back2Back_Histogram with plot parameters
				Back2Back_Histogram(
					data, 
					filename,
					bins,
					ylabel,
					annotate,
					ylim,
					xscale,
					yscale)
		
		if section2 is True:
			"""Plots the relationship between space charge, ir and cyan with RHice"""
			
			plot_data = [[[Air_RH_Liquid, Air_SpaceCharge_Liquid],[Cloud_RH_Liquid, Cloud_SpaceCharge_Liquid]],
						[[Air_RH_Mixed, Air_SpaceCharge_Mixed],[Cloud_RH_Mixed, Cloud_SpaceCharge_Mixed]],
						[[Air_RH_Ice, Air_SpaceCharge_Ice],[Cloud_RH_Ice, Cloud_SpaceCharge_Ice]]]
			
			plot_xlabel = [["RH$_{ice}$ (%)", "RH$_{ice}$ (%)"],
							["RH$_{ice}$ (%)", "RH$_{ice}$ (%)"],
							["RH$_{ice}$ (%)", "RH$_{ice}$ (%)"]]

			plot_ylabel = [["Space Charge (nC m$^{-3}$)", "Space Charge (nC m$^{-3}$)"],
							["Space Charge (nC m$^{-3}$)", "Space Charge (nC m$^{-3}$)"],
							["Space Charge (nC m$^{-3}$)", "Space Charge (nC m$^{-3}$)"]]
							
			plot_annotate = [["Liquid Phase Air", "Liquid Phase Cloud"],
							["Mixed Phase Air", "Mixed Phase Cloud"],
							["Ice Phase Air", "Ice Phase Cloud"]]
			
			plot_color = [["purple", "dodgerblue"],
							["purple", "dodgerblue"],
							["purple", "dodgerblue"]]
			
			filename = self.Storage_Path + 'Plots/Hypothesis_1/RHice_SpaceCharge_AllPhasesClouds_Scatter.png'
				
			
			fontsize = 12
			
			plt.close()
			plt.clf()
			
			f, ax = plt.subplots(3,2,sharex=False,sharey=True)
	
			#Global attributes of subplots
			for subplot in ax.ravel(): subplot.minorticks_on()
			for subplot in ax.ravel(): subplot.grid(which='major',axis='both',c='grey')
			f.subplots_adjust(wspace=0, hspace=0)
			
			#Plot over each data in turn
			plot_num = 0
			for row, (data_row, xlabel_row, ylabel_row, annotate_row, color_row) in enumerate(
				zip(plot_data, plot_xlabel, plot_ylabel, plot_annotate, plot_color)):
						
				hist_plot = zip(np.zeros(2))
				for col, (data, xlabel, ylabel, annotation, color) in enumerate(
							zip(data_row, xlabel_row, ylabel_row, annotate_row, color_row)):
					
					lm = sp.stats.linregress(*data)
					
					plot_num += 1
					color = 'purple' if col == 0 else 'dodgerblue'
					
					#Plot data as Points
					ax[row,col].plot(data[0], data[1], 'p', ms=5, marker='o', markeredgecolor='None', markerfacecolor=color, alpha=1)													  
					
					if col == 0: ax[row,col].set_ylabel(ylabel)
					if row == 2: ax[row,col].set_xlabel(xlabel)

					#Names
					annotation = "" if annotation is None else annotation
					ax[row,col].annotate("(%s) %s" % (gu.alphabet[plot_num-1], 
													  annotation), 
													  xy=(0, 1), 
													  xycoords='axes fraction', 
													  xytext=(20, -20), 
													  textcoords='offset pixels', 
													  horizontalalignment='left', 
													  verticalalignment='top', 
													  fontsize=fontsize)
					
					#Counts
					ax[row,col].annotate("Counts = %.0f\nr = %.5f" % (len(data[0]), 
																		lm[2]), 
																		xy=(1, 1), 
																		xycoords='axes fraction', 
																		xytext=(-20, -20), 
																		textcoords='offset pixels', 
																		horizontalalignment='right', 
																		verticalalignment='top', 
																		fontsize=fontsize)
				
					ax[row,col].set_xlim([0,100]) if col == 0 else ax[row,col].set_xlim([70,130])
					
					ax[row,col].set_ylim([0,100])
					ax[row,col].set_yscale('log')
					#ax[row,col].set_xscale('log')
					
					if row != 2: gu.hide_axis(ax=ax[row,col], x_or_y='x')
					
					
					if col == 1: ax[row,col].xaxis.set_major_locator(MaxNLocator(nbins=len(ax[row,col].get_xticklabels()), prune='lower'))
					
			f.set_size_inches(9, 12) #A4 Size
			
			#Save figure
			plt.savefig(filename, bbox_inches='tight', pad_inches=0.1, dpi=300)

	def Hypothesis2_v2(self):
		"""
		HYPOTHESIS 2: The charge present within a convective cloud is proportional to the 
		change in PG measured at the surface.
		
		THIS METHOD WILL USE THE SIGN CHANGE TO PLACE THE POINT CHARGES
		"""
		
		if self.verbose is True: gu.cprint("[INFO] You are running PointCharge from the DEV release", type='bold')
		
		############################################################################
		"""Prerequisites"""
		
		# Time Controls
		t_begin = time.time()
		
		# Constants
		k 			= 2500000/22468879568420441	#Coulombs Constant (exact value!)
		kn2ms		= 0.5144					#Conversion between knots and m/s

		Sensor = self.sensor_package
		
		# Radiosonde Data
		Radiosonde_Data = self.Radiosonde_Data[Sensor]['Units'].copy()
		Clouds_ID = self.Clouds_ID[Sensor].copy()
		
		# Set-up data importer
		EPCC_Data = EPCC_Importer()
		
		# Get Cloud and Clear-Air Heights
		Cloud_Heights, Clear_Heights = self._CloudHeights(sensor=Sensor, method='Zhang')

		############################################################################
		"""Pre-Condition Data"""
		
		# Remove nan's from Time, Height, Wind, SpaceCharge
		Time, Height, Wind, SpaceCharge = gu.antifinite((Radiosonde_Data['time'], 
			Radiosonde_Data['height'],
			Radiosonde_Data['WindSpeed'],
			Radiosonde_Data['SpaceCharge']), 
			unpack=True)
				
		# Detect sign changes in data
		SignChange = np.where(np.diff(np.sign(SpaceCharge)))[0]
		
		# Get index of lowest cloud
		# CloudIndex = gu.searchsorted(Radiosonde_Data['height'], Cloud_Heights[0])
		CloudIndex = gu.searchsorted(Radiosonde_Data['height'], [0,12])
			
		# Get SignChange position for cloud
		Cloud_SignChange = SignChange[(SignChange >= CloudIndex[0]) & (SignChange <= CloudIndex[1])]
		
		# Get time stamps of sign change
		Cloud_TimeChange = Time[Cloud_SignChange]
		
		# Broadcast Cloud_SignChange into a 2D array which is easier to 
		# use with for loops.
		Cloud_SignChange = gu.broadcast(Cloud_SignChange,2,1) + 1
		
		############################################################################
		"""Set-up electric field environment"""
		
		# [1] SPACE CHARGE DENSITY
		# Calculate the 95th percentile of the space charge density between
		# each polarity inversion. Making sure to conserve local sign.
		Cloud_SpaceCharge = np.zeros(Cloud_SignChange.shape[0])
		for i,  space in enumerate(Cloud_SignChange):
			Local_SpaceCharge = SpaceCharge[space[0]:space[1]]
			Local_Sign = sp.stats.mode(np.sign(Local_SpaceCharge))[0][0]
			Cloud_SpaceCharge[i] = Local_Sign*np.nanpercentile(np.abs(Local_SpaceCharge), 100)
		
		# Convert space charge from pC to C
		Cloud_SpaceCharge /= 10**12
		
		# [2] POINT CHARGE HEIGHT
		# Calculate the height positions for each point charge. i.e. between 
		# each sign change the absolute maximum space charge value is found
		# and then indexed onto the height array.
		Cloud_Height = np.zeros(Cloud_SignChange.shape[0])
		for i, space in enumerate(Cloud_SignChange):
			
			# Get the local index of the absolute maximum space charge density
			mask = np.argmax(np.abs(SpaceCharge[space[0]:space[1]]))
			
			# Find the height using 'mask' on the same subsetted data
			PC_Height = Height[space[0]:space[1]][mask]
			
			# Determine the horizontal distance between RUAO and Point Charge.
			Cloud_Height[i] = ((Radiosonde_Data['range'][space[0]:space[1]][mask]/1000)**2 + PC_Height**2)**0.5
				
		# Convert heights from km to m
		Cloud_Height *= 1000
		
		# [3] POINT CHARGE AREA
		# Calculate the area that each point charge corresponds to. Here
		# we use the vertical height gained between sign changes.
		Cloud_AscentArea = np.array([Height[space[1]] - Height[space[0]] for space in Cloud_SignChange], dtype=np.float64)*1000
		
		# [4] CLOUD CHARGE
		# Now calculate the charge within the area.
		Cloud_Charge = Cloud_SpaceCharge * (4/3)*np.pi*Cloud_AscentArea**3 # * 3
		
		# [5] CLOUD VELOCITY
		# Calculate the velocity of each point charge.
		Cloud_Velocity = np.array([np.nanmean(Wind[space[0]:space[1]]) for space in Cloud_SignChange], dtype=np.float64) # /4.5
		
		# [6] CLOUD TIME
		# Specify the time range in seconds to calculate the electric field over.
		# The time range revolves around the first point charge specified,
		# therefore, Cloud_Time is typically specified with +- bounds. 
		Cloud_Time = np.arange(-3000, 3000, 1)
		
		# [7] CLOUD TIME DIFFERENCE
		# Get the time for each point charge.
		Cloud_TimeDiff = np.zeros(Cloud_SignChange.shape[0])
		for i, space in enumerate(Cloud_SignChange):
			
			# Get the local index of the absolute maximum space charge density
			mask = np.argmax(np.abs(SpaceCharge[space[0]:space[1]]))
			
			# Find the height using 'mask' on the same subsetted data
			Cloud_TimeDiff[i] = Time[space[0]:space[1]][mask]
		Cloud_TimeDiff -= Cloud_TimeDiff[0]

		############################################################################
		"""Calculate the electric field"""
		
		# [8] ELECTRIC FIELD CALCULATION
		# Now the Cloud_Time, Cloud_TimeDiff, Cloud_Velocity, Cloud_Height and 
		# Cloud_Charge has been calculated, the electric field can now be found
		Cloud_ElectricField = zip(np.zeros(Cloud_SignChange.shape[0]))
		for i, (time_diff, height, velocity, charge) in enumerate(
				zip(Cloud_TimeDiff, Cloud_Height, Cloud_Velocity, Cloud_Charge)):
			
			#Cloud_ElectricField[i] = (gu.cosarctan(((Cloud_Time+time_diff)*velocity)/height)*charge)/(k*height**2)
			Cloud_ElectricField[i] = (gu.cosarctan(((Cloud_Time-time_diff)*velocity)/height)*charge)/(k*height**2)
			
		# Add the background electric field to the calculations. For now we can
		# assume the background electric field is 100 V/m.
		Cloud_ElectricField_Total = 0 + np.nansum(Cloud_ElectricField, axis=0)
		
		############################################################################
		"""Determine the time stamp data for the flight"""
		
		# Get the launch date for the radiosonde.
		LaunchDate = self.LaunchTime[int(Sensor)].astype('datetime64[D]')
		
		# Get the time when the radiosonde reached the cloud base
		Cloud_BaseTime = self.LaunchTime[int(Sensor)] + np.timedelta64(int(Radiosonde_Data['time'][CloudIndex[0]]), 's')

		# Calculate datetimes for each calculation in Cloud_ElectricField_Total
		Cloud_DateTime = Cloud_BaseTime + Cloud_Time.astype('timedelta64[s]')
		
		# Import PG data from the RUAO.
		ID = np.where(Data['Date_ID'] == Cloud_BaseTime.astype('datetime64[D]').astype('datetime64[s]').astype(datetime))[0][0]
		Field_Mill_Time, Field_Mill_PG = EPCC_Data.FieldMill_Calibrate(self.data['FieldMill_RUAO_1sec_Processed_File'][ID], hours2dt=True)

		# Subset PG to match Estimated Electric Field
		mask = (Field_Mill_Time >= Cloud_DateTime[0]) & (Field_Mill_Time <= Cloud_DateTime[-1])
		Field_Mill_Time = Field_Mill_Time[mask]
		Field_Mill_PG = Field_Mill_PG[mask]
		
		############################################################################
		"""Calculate Statistics"""
		
		Test = gu.antifinite((Field_Mill_PG, Cloud_ElectricField_Total))
		print("Test", Test)
		print("R-Squared =", gu.R1to1(*Test))
		#print(sp.stats.anderson_ksamp((Test[0], Test[1])))
		print("PearsonrResult", sp.stats.pearsonr(*Test))
		print(sp.stats.spearmanr(*Test))
		
		############################################################################
		"""Plot the electric field"""
		
		#Plot the data
		gu.backend_changer()
		
		plt.close()
		plt.clf()
		
		f, ax1 = plt.subplots()
		
		ax1.plot(Cloud_DateTime, Cloud_ElectricField_Total)
		
		ax2 = ax1.twinx()
		
		ax2.plot(Field_Mill_Time, Field_Mill_PG, lw=0.5, color='black')
		
		ax1.grid(which='major',axis='both',c='grey')
		ax1.set_xlabel('Time (Hour)')
		ax1.set_ylabel('Estimated Potential Gradient (V/m)')
		ax2.set_ylabel('Measured Potential Gradient (V/m)')
		ax1.set_title('Radiosonde Package No.%s' % Sensor)
		
		ax1.set_xlim(np.min(Cloud_DateTime), np.max(Cloud_DateTime))
		ax2.set_xlim(np.min(Cloud_DateTime), np.max(Cloud_DateTime))

		ax1.set_ylim(np.nanmin(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])), np.nanmax(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])))
		ax2.set_ylim(np.nanmin(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])), np.nanmax(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])))
		ax1.xaxis.set_major_formatter(DateFormatter('%H:%M'))
		
		ax1.get_yaxis().get_major_formatter().set_useOffset(False)
		ax1.get_yaxis().get_major_formatter().set_scientific(False)
		
		#plt.gcf().set_size_inches((11.7/6), 8.3)
		
		#Save figure
		filename = self.Storage_Path + 'Plots/Hypothesis_2/ElectricField_Estimate_RadiosondeNo.%s.png' % Sensor.rjust(2, '0')
		plt.savefig(filename, bbox_inches='tight', pad_inches=0.1, dpi=300)		
		
		############################################################################
		"""Plot the decoupled Electric Field"""
		
		plt.close()
		plt.clf()
		
		f, ax1 = plt.subplots()
		
		for ElectricField in Cloud_ElectricField:
			ax1.plot(Cloud_DateTime, ElectricField, lw=0.5, color='black')
		
		
		ax1.grid(which='major',axis='both',c='grey')
		ax1.set_xlabel('Time (Hour)')
		ax1.set_ylabel('Estimated Potential Gradient (V/m)')
		ax1.set_title('Radiosonde Package No.%s' % Sensor)
		
		ax1.set_xlim(np.min(Cloud_DateTime), np.max(Cloud_DateTime))
		
		ax1.set_ylim(np.nanmin(Cloud_ElectricField), np.nanmax(Cloud_ElectricField))
		ax1.xaxis.set_major_formatter(DateFormatter('%H:%M'))
		
		ax1.get_yaxis().get_major_formatter().set_useOffset(False)
		ax1.get_yaxis().get_major_formatter().set_scientific(False)
		
		#Save figure
		filename = self.Storage_Path + 'Plots/Hypothesis_2/ElectricField_Estimate_RadiosondeNo.%s_Decoupled.png' % Sensor.rjust(2, '0')
		plt.savefig(filename, bbox_inches='tight', pad_inches=0.1, dpi=300)		
		
	def Hypothesis2(self):
		"""
		HYPOTHESIS 2: The charge present within a convective cloud is proportional to the 
		change in PG measured at the surface.
		"""
		
		if self.verbose is True: gu.cprint("[INFO] You are running PointCharge from the DEV release", type='bold')
		
		############################################################################
		"""Prerequisites"""
		
		#Time Controls
		t_begin = time.time()
		
		#Constants
		k 			= 2500000/22468879568420441	#Coulombs Constant (exact value!)
		kn2ms		= 0.5144					#Conversion between knots and m/s
		
		#Radiosonde Data
		Radiosonde_Data = self.Radiosonde_Data['5']['Units'].copy()
		Clouds_ID = self.Clouds_ID['5'].copy()
		
		#Set-up data importer
		EPCC_Data = EPCC_Importer()
		
		# Get Cloud and Clear-Air Heights
		Cloud_Heights, Clear_Heights = self._CloudHeights(sensor=5, method='Zhang')
		
		############################################################################
		
		print("Cloud_Heights", Cloud_Heights)
		
		#Get index of lowest cloud
		CloudIndex = gu.searchsorted(Radiosonde_Data['height'], Cloud_Heights[0])
		
		elem = 1
		
		#Find total charge
		Cloud_SpaceChargeDensity = Radiosonde_Data['Log_SpaceCharge'][CloudIndex[0]:CloudIndex[1]]
		Cloud_AscentArea = np.diff(Radiosonde_Data['height'][CloudIndex[0]:CloudIndex[1]+1])*1000#/np.diff(Radiosonde_Data['time'][CloudIndex[0]:CloudIndex[1]+1])
		Cloud_Charge = gu.interavg(Cloud_SpaceChargeDensity, elem, type='nansum') * gu.interavg(Cloud_AscentArea, elem, type='nansum')
		
		gu.stats(Cloud_Charge, output=True)
		
		#Get Cloud Height [m]
		Cloud_Height = gu.interavg(Radiosonde_Data['height'][CloudIndex[0]:CloudIndex[1]]*1000, elem, type='nanmean')
		
		#Get Cloud Velocity [m/s]
		Cloud_Velocity = gu.interavg(np.sqrt(Radiosonde_Data['u']**2+Radiosonde_Data['v']**2)[CloudIndex[0]:CloudIndex[1]], elem, type='nanmean')
		
		#Get Cloud Time
		Cloud_Time = np.datetime64(self.Radiosonde_Data['5']['Date'])
		Cloud_Date = Cloud_Time.astype('datetime64[D]')
		Cloud_BaseTime = Cloud_Time + np.timedelta64(int(Radiosonde_Data['time'][CloudIndex[0]]), 's')
		
		#Get Cloud Time Difference
		Cloud_TimeDiff = gu.interavg(Radiosonde_Data['time'][CloudIndex[0]:CloudIndex[1]], elem, type='nanmean')
		Cloud_TimeDiff -= Cloud_TimeDiff[0]
		
		#Calculate Electric Field
		print(Cloud_Height.shape, Cloud_Velocity.shape, Cloud_Charge.shape)
		
		Cloud_Time = np.arange(-2000, 2000, 10)
		
		Cloud_ElectricField = np.array([(gu.cosarctan(((Cloud_Time+time_diff)*velocity)/height)*charge)/(k*height**2) for time_diff, height, velocity, charge in zip(Cloud_TimeDiff, Cloud_Height, Cloud_Velocity, Cloud_Charge)])
		
		print("Cloud_ElectricField", Cloud_ElectricField.shape)
		
		Cloud_ElectricField_Total = 100 + np.nansum(Cloud_ElectricField, axis=0)
		
		print("Cloud_ElectricField_Total", Cloud_ElectricField_Total.shape)
		
		#Calculate datetimes for each calculation in Cloud_ElectricField
		Cloud_DateTime = Cloud_BaseTime + Cloud_Time.astype('timedelta64[s]')
		
		#Import PG data
		ID = np.where(Data['Date_ID'] == Cloud_BaseTime.astype('datetime64[D]').astype('datetime64[s]').astype(datetime))[0][0]
		Field_Mill_Time, Field_Mill_PG = EPCC_Data.FieldMill_Calibrate(self.data['FieldMill_RUAO_1sec_Processed_File'][ID])
		
		#Plot the data
		gu.backend_changer()
		
		plt.close()
		plt.clf()
		
		f, ax1 = plt.subplots()
		
		ax1.plot(Cloud_DateTime, Cloud_ElectricField_Total)
		
		ax2 = ax1.twinx()
		Field_Mill_Time = gu.addHourFrac(Cloud_Date, Field_Mill_Time)
		print("Field_Mill_Time", Field_Mill_Time)
		ax2.plot(Field_Mill_Time, Field_Mill_PG, lw=0.5, color='black')
		
		ax1.grid(which='major',axis='both',c='grey')
		ax1.set_xlabel('Time (Hour)')
		ax1.set_ylabel('Estimated Potential Gradient (V/m)')
		ax2.set_ylabel('Measured Potential Gradient (V/m)')
		
		ax1.set_xlim(np.min(Cloud_DateTime), np.max(Cloud_DateTime))
		ax2.set_xlim(np.min(Cloud_DateTime), np.max(Cloud_DateTime))

		#ax1.set_ylim(np.nanmin(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])), np.nanmax(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])))
		#ax2.set_ylim(np.nanmin(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])), np.nanmax(gu.flatten([Cloud_ElectricField_Total,Field_Mill_PG])))
		ax1.xaxis.set_major_formatter(DateFormatter('%H:%M'))
		
		ax1.get_yaxis().get_major_formatter().set_useOffset(False)
		ax1.get_yaxis().get_major_formatter().set_scientific(False)
		
		#plt.gcf().set_size_inches((11.7/6), 8.3)
		
		plt.show()
	
		sys.exit()
	
	def Hypothesis3(self):
		"""
		HYPOTHESIS 3: The charge present within a convective clouds has a positive correlation 
		with optical thickness caused by an increase in the hydrometeor collision efficiency which 
		in turn increases the amount of charge separation.
		"""
		
		if self.verbose is True: gu.cprint("[INFO] You are running PointCharge from the DEV release", type='bold')
		
		############################################################################
		"""Prerequisites"""
		
		#Time Controls
		t_begin = time.time()
		
		#Radiosonde Data
		Radiosonde_Data = self.Radiosonde_Data.copy()
		Clouds_ID = self.Clouds_ID.copy()
		LayerType = self.LayerType.copy()
		
		#Set-up data importer
		EPCC_Data = EPCC_Importer()
		
		#Set-up plotting
		gu.backend_changer()
		
		#Conditionals
		section1 = False
		section2 = False
		section3 = True
				
		if section1 is True:
			############################################################################
			"""[SECTION 1] Space Charge vs. IR"""
			
			#Arrays
			Cloud_SpaceCharge = gu.array()
			Cloud_IR = gu.array()
			Cloud_Cyan = gu.array()
			Cloud_IRdiffCyan = gu.array()
			Cloud_IRdivCyan = gu.array()

			Sensor_Package = np.arange(3,11).astype('S2')
			#Sensor_Package = ['4']
			for sensor in Sensor_Package:
				
				#Check the sensor has been processed by _RadiosondeImporter
				try:
					Radiosonde_Data[sensor]
				except KeyError:
					if self.verbose is True: print("[Warning] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (sensor))
					continue
				
				############################################################################
				"""Get limits of cloud and non cloud areas"""
				
				#IR = Radiosonde_Data[sensor]['Units']['IR']
				#Clouds_ID[sensor] = gu.contiguous((IR > np.nanpercentile(IR, 80)).astype(int), invalid=0)
				
				# Get cloud base and cloud top heights for each identified cloud
				Cloud_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][-1]] for Cloud in np.unique(Clouds_ID[sensor])[1:]], dtype=np.float64)
				
				# Get clear areas
				Clear_ID = gu.argcontiguous(LayerType[sensor], valid=0)
				#Clear_ID = gu.contiguous((IR < np.nanpercentile(IR, 20)).astype(int), invalid=0)
				Clear_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][-1]] for Cloud in np.unique(Clear_ID)[1:]], dtype=np.float64)
								
				############################################################################
				
				#Remove nan's from data
				Time, Height, SpaceCharge, IR, Cyan, IRdiffCyan, IRdivCyan = gu.antifinite((Radiosonde_Data[sensor]['Units']['time'], 
					Radiosonde_Data[sensor]['Units']['height'],
					np.abs(Radiosonde_Data[sensor]['Units']['SpaceCharge']),
					Radiosonde_Data[sensor]['Units']['IR'],
					Radiosonde_Data[sensor]['Units']['Cyan'],
					(Radiosonde_Data[sensor]['Units']['IR']-Radiosonde_Data[sensor]['Units']['Cyan']),
					(Radiosonde_Data[sensor]['Units']['IR']/Radiosonde_Data[sensor]['Units']['Cyan'])),
					unpack=True)
			
				for cloud in Cloud_Heights:
				
					#Get index of lowest cloud
					CloudIndex = gu.searchsorted(Height, cloud)
				
					#Subset data
					SpaceCharge_Subset = SpaceCharge[CloudIndex[0]:CloudIndex[1]]
					IR_Subset = IR[CloudIndex[0]:CloudIndex[1]]
					Cyan_Subset = Cyan[CloudIndex[0]:CloudIndex[1]]
					IRdiffCyan_Subset = IRdiffCyan[CloudIndex[0]:CloudIndex[1]]
					IRdivCyan_Subset = IRdivCyan[CloudIndex[0]:CloudIndex[1]]

					#Add to master array
					Cloud_SpaceCharge.update([SpaceCharge_Subset])
					Cloud_IR.update([IR_Subset])
					Cloud_Cyan.update([Cyan_Subset])
					Cloud_IRdiffCyan.update([IRdiffCyan_Subset])
					Cloud_IRdivCyan.update([IRdivCyan_Subset])
			
			#Finalize arrays
			Cloud_SpaceCharge = Cloud_SpaceCharge.finalize(dtype=np.float64)/1000
			Cloud_IR = Cloud_IR.finalize(dtype=np.float64)
			Cloud_Cyan = Cloud_Cyan.finalize(dtype=np.float64)
			Cloud_IRdiffCyan = Cloud_IRdiffCyan.finalize(dtype=np.float64)
			Cloud_IRdivCyan = Cloud_IRdivCyan.finalize(dtype=np.float64)
			
			mask = (Cloud_IR < 5) & (Cloud_SpaceCharge < 40)
			Cloud_SpaceCharge = Cloud_SpaceCharge[mask]
			Cloud_IR = Cloud_IR[mask]
			Cloud_Cyan = Cloud_Cyan[mask]
			Cloud_IRdiffCyan = Cloud_IRdiffCyan[mask]
			Cloud_IRdivCyan = Cloud_IRdivCyan[mask]
			
			#LR_IRSC = sp.stats.linregress(Cloud_SpaceCharge, Cloud_IR)
			#LR_IRSC = gu.HuberRegression(Cloud_SpaceCharge, Cloud_IR)
			
			#print("LR_IRSC", LR_IRSC)
			#print("Correlation", sp.stats.spearmanr(Cloud_SpaceCharge, Cloud_IR)[0])
			
			#Cloud_SpaceCharge2, Cloud_IR, _ = gu.ensemble(Cloud_SpaceCharge, Cloud_IR, 100, method='unique', undersample=True, slim=True)
			filename = self.Storage_Path + 'Plots/Hypothesis_3/CrossCorrelation_SpaceCharge_IR_AllRadiosondes_UnAveraged.png'
			Cloud_SpaceCharge_Best, Cloud_IR_Best = CrossCorrelation_Scatter_Plot(
				Cloud_SpaceCharge, 
				Cloud_IR, 
				filename=filename, 
				xlabel="Space Charge (nC m$^{-3}$)", 
				ylabel="IR Cloud Sensor (V)", 
				title="Cross Correlation (Radiosonde No.3,4,5,9,10)",
				xlim='auto',
				ylim=[0,'auto'],
				xscale="linear",
				yscale="linear",
				verbose=True)
			
			#Cloud_SpaceCharge2, Cloud_Cyan, _ = gu.ensemble(Cloud_SpaceCharge, Cloud_Cyan, 100, method='unique', undersample=True, slim=True)
			filename = self.Storage_Path + 'Plots/Hypothesis_3/CrossCorrelation_SpaceCharge_Cyan_AllRadiosondes_UnAveraged.png'
			Cloud_SpaceCharge_Best, Cloud_IR_Best = CrossCorrelation_Scatter_Plot(
				Cloud_SpaceCharge, 
				Cloud_Cyan, 
				filename=filename, 
				xlabel="Space Charge (nC m$^{-3}$)", 
				ylabel="Cyan Cloud Sensor (V)", 
				title="Cross Correlation (Radiosonde No.3,4,5,9,10)",
				xlim='auto',
				ylim=[0,'auto'],
				xscale="linear",
				yscale="linear",
				verbose=True)
			
			#Cloud_SpaceCharge2, Cloud_IRdiffCyan, _ = gu.ensemble(Cloud_SpaceCharge, Cloud_IRdiffCyan, 100, method='unique', undersample=True, slim=True)
			filename = self.Storage_Path + 'Plots/Hypothesis_3/CrossCorrelation_SpaceCharge_IRdiffCyan_AllRadiosondes_UnAveraged.png'
			Cloud_SpaceCharge_Best, Cloud_IR_Best = CrossCorrelation_Scatter_Plot(
				Cloud_SpaceCharge, 
				Cloud_IRdiffCyan, 
				filename=filename, 
				xlabel="Space Charge (nC m$^{-3}$)", 
				ylabel="IR - Cyan Cloud Sensor (V)", 
				title="Cross Correlation (Radiosonde No.3,4,5,9,10)",
				xlim='auto',
				ylim=[0,'auto'],
				xscale="linear",
				yscale="linear",
				verbose=True)
				
			#Cloud_SpaceCharge2, Cloud_IRdivCyan, _ = gu.ensemble(Cloud_SpaceCharge, Cloud_IRdivCyan, 100, method='unique', undersample=True, slim=True)
			filename = self.Storage_Path + 'Plots/Hypothesis_3/CrossCorrelation_SpaceCharge_IRdivCyan_AllRadiosondes_UnAveraged.png'
			Cloud_SpaceCharge_Best, Cloud_IR_Best = CrossCorrelation_Scatter_Plot(
				Cloud_SpaceCharge, 
				Cloud_IRdivCyan, 
				filename=filename, 
				xlabel="Space Charge (nC m$^{-3}$)", 
				ylabel="IR/Cyan Cloud Sensor (V)", 
				title="Cross Correlation (Radiosonde No.3,4,5,9,10)",
				xlim='auto',
				ylim=[0,'auto'],
				xscale="linear",
				yscale="linear",
				verbose=True)
			
			#LR_IRSC2 = sp.stats.linregress(Cloud_SpaceCharge_Best,Cloud_IR_Best)
			LR_IRSC2 = gu.HuberRegression(Cloud_SpaceCharge_Best,Cloud_IR_Best)
		
			print("LR_IRSC2", LR_IRSC2)
			print("Correlation", sp.stats.spearmanr(Cloud_SpaceCharge_Best, Cloud_IR_Best)[0])
		
			sys.exit()
		
		if section2 is True:
			############################################################################
			"""[SECTION 1] Space Charge vs. SLWC"""
			
			#Arrays
			Cloud_Tdry = gu.array()
			Cloud_SpaceCharge = gu.array()
			Cloud_SLWC = gu.array()
			
			#Sensor_Package = np.arange(3,11).astype('S2')
			Sensor_Package = np.arange(3,6).astype('S2')
			#Sensor_Package = ['4']
			for sensor in Sensor_Package:
				
				#Check the sensor has been processed by _RadiosondeImporter
				try:
					Radiosonde_Data[sensor]
				except KeyError:
					if self.verbose is True: print("[Warning] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (sensor))
					continue
				
				############################################################################
				"""Get limits of cloud and non cloud areas"""
				
				#IR = Radiosonde_Data[sensor]['Units']['IR']
				#Clouds_ID[sensor] = gu.contiguous((IR > np.nanpercentile(IR, 80)).astype(int), invalid=0)
				
				# Get cloud base and cloud top heights for each identified cloud
				Cloud_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][-1]] for Cloud in np.unique(Clouds_ID[sensor])[1:]], dtype=np.float64)
				
				# Get clear areas
				Clear_ID = gu.argcontiguous(LayerType[sensor], valid=0)
				#Clear_ID = gu.contiguous((IR < np.nanpercentile(IR, 20)).astype(int), invalid=0)
				Clear_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][-1]] for Cloud in np.unique(Clear_ID)[1:]], dtype=np.float64)
								
				############################################################################
				
				#Remove nan's from data
				Time, Height, Tdry, SpaceCharge, SLWC = gu.antifinite((Radiosonde_Data[sensor]['Units']['time'], 
					Radiosonde_Data[sensor]['Units']['height'],
					Radiosonde_Data[sensor]['Units']['Tdry'],
					np.abs(Radiosonde_Data[sensor]['Units']['SpaceCharge']),
					Radiosonde_Data[sensor]['Units']['SLWC']), 
					unpack=True)
			
				for cloud in Cloud_Heights:
				
					#Get index of lowest cloud
					CloudIndex = gu.searchsorted(Height, cloud)
				
					#Subset data
					Tdry_Subset = Tdry[CloudIndex[0]:CloudIndex[1]]
					SpaceCharge_Subset = SpaceCharge[CloudIndex[0]:CloudIndex[1]]
					SLWC_Subset = SLWC[CloudIndex[0]:CloudIndex[1]]
					
					#Add to master array
					Cloud_Tdry.update([Tdry_Subset])
					Cloud_SpaceCharge.update([SpaceCharge_Subset])
					Cloud_SLWC.update([SLWC_Subset])
			
			#Finalize arrays
			Cloud_Tdry = Cloud_Tdry.finalize(dtype=np.float64)
			Cloud_SpaceCharge = Cloud_SpaceCharge.finalize(dtype=np.float64)/1000
			Cloud_SLWC = Cloud_SLWC.finalize(dtype=np.float64)
			
			#mask = (Cloud_IR < 5) & (Cloud_SpaceCharge < 40)
			mask = (Cloud_SpaceCharge < 40)
			Cloud_Tdry = Cloud_Tdry[mask]
			Cloud_SpaceCharge = Cloud_SpaceCharge[mask]
			Cloud_SLWC = Cloud_SLWC[mask]
			
			Cloud_SpaceCharge2, Cloud_SLWC, _ = gu.ensemble(Cloud_SpaceCharge, Cloud_SLWC, 50, method='unique', undersample=True, slim=True)
			filename = self.Storage_Path + 'Plots/Hypothesis_3/CrossCorrelation_SpaceCharge_SLWC_AllRadiosondes_UnAveraged.png'
			Cloud_SpaceCharge_Best, Cloud_IR_Best = CrossCorrelation_Scatter_Plot(
				Cloud_SpaceCharge2, 
				Cloud_SLWC, 
				filename=filename, 
				xlabel="Space Charge (nC m$^{-3}$)", 
				ylabel="Liquid Water Sensor (g m$^{-1}$)", 
				title="Cross Correlation (Radiosonde No.3,4,5)",
				xlim='auto',
				ylim=[0,'auto'],
				xscale="linear",
				yscale="linear",
				verbose=True)
			
			gu.stats(Cloud_Tdry, output=True)
			
			#Cloud_SpaceCharge2, Cloud_Tdry, _ = gu.ensemble(Cloud_SpaceCharge, Cloud_Tdry, 50, method='unique', undersample=True, slim=True)
			filename = self.Storage_Path + 'Plots/Hypothesis_3/CrossCorrelation_Tdry_SLWC_AllRadiosondes_UnAveraged.png'
			Cloud_SpaceCharge_Best, Cloud_IR_Best = CrossCorrelation_Scatter_Plot(
				Cloud_Tdry, 
				Cloud_SLWC, 
				filename=filename, 
				xlabel="Temperature (C)", 
				ylabel="Liquid Water Sensor (g m$^{-1}$)", 
				title="Cross Correlation (Radiosonde No.3,4,5)",
				xlim='auto',
				ylim='auto',
				xscale="linear",
				yscale="linear",
				verbose=True)
				
		if section3 is True:
			############################################################################
			"""[SECTION 3] Space Charge Fluctuations"""
			
			# Initalise the arrays to store the signchange and space charge data
			Cloud_SignChange_All = gu.array()
			Cloud_SpaceCharge_All = gu.array()
			Air_SignChange_All = gu.array()
			Air_SpaceCharge_All = gu.array()
			
			# Calculate 95th percentile of Space Charge between each sign change
			# for all sign changes that occur within clouds and clear air. Two
			# methods are used to define a "cloud". First, is the Zhang method
			# which used RH w.r.t. ice. Second, the IR cloud sensor which can
			# identify areas of the atmosphere with a high return signal. For
			# this method a 80-20 percentile split is used to differentiate
			# clearly between cloud and clear-air regions.
			
			Sensor_Package = np.arange(3,11).astype('S2')
			#Sensor_Package = ['4']
			for sensor in Sensor_Package:
				
				#Check the sensor has been processed by _RadiosondeImporter
				try:
					Radiosonde_Data[sensor]
				except KeyError:
					if self.verbose is True: print("[Warning] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (sensor))
					continue
				
				############################################################################
				"""Get limits of cloud and non cloud areas"""
				
				#IR = Radiosonde_Data[sensor]['Units']['IR']
				#Clouds_ID[sensor] = gu.contiguous((IR > np.nanpercentile(IR, 80)).astype(int), invalid=0)
				
				# Get cloud base and cloud top heights for each identified cloud
				Cloud_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clouds_ID[sensor] == Cloud][-1]] for Cloud in np.unique(Clouds_ID[sensor])[1:]], dtype=np.float64)
				
				# Get clear areas
				Clear_ID = gu.argcontiguous(LayerType[sensor], valid=0)
				#Clear_ID = gu.contiguous((IR < np.nanpercentile(IR, 20)).astype(int), invalid=0)
				Clear_Heights = np.array([[Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][0], Radiosonde_Data[sensor]['Units']['height'][Clear_ID == Cloud][-1]] for Cloud in np.unique(Clear_ID)[1:]], dtype=np.float64)
								
				############################################################################
				"""Import data and calculate 95th percentile space charge"""
				
				#Remove nan's from data
				Time, Height, SpaceCharge = gu.antifinite((Radiosonde_Data[sensor]['Units']['time'], 
					Radiosonde_Data[sensor]['Units']['height'],
					Radiosonde_Data[sensor]['Units']['SpaceCharge']/1000), 
					unpack=True)
						
				#Detect sign changes in data
				SignChange = np.where(np.diff(np.sign(SpaceCharge)))[0]
				
				# Cloudy Regions
				for cloud in Cloud_Heights:
				
					#Get index of lowest cloud
					CloudIndex = gu.searchsorted(Height, cloud)
					
					#Get SignChange position for cloud
					Cloud_SignChange = SignChange[(SignChange >= CloudIndex[0]) & (SignChange <= CloudIndex[1])]
					
					#Get time stamps of sign change
					Cloud_TimeChange = Time[Cloud_SignChange]
					
					#Get Space Charge
					Spacing = gu.broadcast(Cloud_SignChange,2,1)
					Cloud_SpaceCharge = np.array([np.nanpercentile(np.abs(SpaceCharge[space[0]:space[1]]), 95) for space in Spacing])
						
					#Get difference
					Cloud_SignChange_All.update([np.diff(Cloud_TimeChange)])
					Cloud_SpaceCharge_All.update([Cloud_SpaceCharge])
				
				# Clear-Air Regions
				for air in Clear_Heights:
				
					#Get index of lowest cloud
					AirIndex = gu.searchsorted(Height, air)
					
					#Get SignChange position for cloud
					Air_SignChange = SignChange[(SignChange >= AirIndex[0]) & (SignChange <= AirIndex[1])]
					
					#Get time stamps of sign change
					Air_TimeChange = Time[Air_SignChange]
					
					#Get Space Charge
					Spacing = gu.broadcast(Air_SignChange,2,1)
					Air_SpaceCharge = np.array([np.nanpercentile(np.abs(SpaceCharge[space[0]:space[1]]), 95) for space in Spacing])
						
					#Get difference
					Air_SignChange_All.update([np.diff(Air_TimeChange)])
					Air_SpaceCharge_All.update([Air_SpaceCharge])
				
				############################################################################
				
			# Finalise arrays
			Cloud_SignChange_All = Cloud_SignChange_All.finalize(dtype=np.float64)
			Cloud_SpaceCharge_All = Cloud_SpaceCharge_All.finalize(dtype=np.float64)
			Air_SignChange_All = Air_SignChange_All.finalize(dtype=np.float64)
			Air_SpaceCharge_All = Air_SpaceCharge_All.finalize(dtype=np.float64)
			
			# Mask extremely large space charge values
			mask = Cloud_SpaceCharge_All < 40
			Cloud_SignChange_All = Cloud_SignChange_All[mask]
			Cloud_SpaceCharge_All = Cloud_SpaceCharge_All[mask]
			
			mask = Air_SpaceCharge_All < 40
			Air_SignChange_All = Air_SignChange_All[mask]
			Air_SpaceCharge_All = Air_SpaceCharge_All[mask]
			
			############################################################################
			"""Perform some statistical tests"""
			
			#Anderson-Darling Test
			print(sp.stats.anderson_ksamp((Cloud_SignChange_All, Air_SignChange_All)))
			print("PearsonrResult", sp.stats.pearsonr(Cloud_SignChange_All, Cloud_SpaceCharge_All))
			print(sp.stats.spearmanr(Cloud_SignChange_All, Cloud_SpaceCharge_All))

			#Linear Regressions
			Cloud_LM = sp.stats.linregress(Cloud_SignChange_All, Cloud_SpaceCharge_All)
			Air_LM = sp.stats.linregress(Air_SignChange_All, Air_SpaceCharge_All)
			All_LM = sp.stats.linregress(np.hstack((Cloud_SignChange_All, Air_SignChange_All)), 
				np.hstack((Cloud_SpaceCharge_All, Air_SpaceCharge_All)))
			
			print("Cloud:", Cloud_LM)
			print("Air:", Air_LM)
			print("All:", All_LM)
			
			############################################################################
			"""
			Plot the results of the relationship between sign change and space 
			charge for both cloud and clear-air regions
			"""
			
			fontsize = 10
			
			# Set-up plot
			plt.clf()
			plt.close()
			f, ax = plt.subplots(1, 2)
			
			# Set global properties before the plotting of data
			for subplot in ax: subplot.grid(which='major',axis='both',c='grey')
			f.subplots_adjust(wspace=0)
			ax[1].axes.tick_params(left='off')
			
			# Plot data			
			ax[1].plot(Cloud_SignChange_All, Cloud_SpaceCharge_All,  'p', ms=5, marker='o', markeredgecolor='None', markerfacecolor='dodgerblue', alpha=1)													  
			ax[0].plot(Air_SignChange_All, Air_SpaceCharge_All,  'p', ms=5, marker='o', markeredgecolor='None', markerfacecolor='purple', alpha=1)													  
			
			# Specify the x and y labels
			ax[0].set_xlabel("Time between Polarity Changes (s)")
			ax[0].set_ylabel("95th Percentile Space Charge Density (nC m$^{-3}$)")
			ax[1].set_xlabel("Time between Polarity Changes (s)")
			
			# Force both subplots to have same x and y limits
			all_xdata = np.hstack((Cloud_SignChange_All, Air_SignChange_All))
			all_ydata = np.hstack((Cloud_SpaceCharge_All, Air_SpaceCharge_All))
			ax[0].set_xlim([np.nanmin(all_xdata), np.nanmax(all_xdata)])
			ax[0].set_ylim([np.nanmin(all_ydata), np.nanmax(all_ydata)])
			ax[1].set_xlim([np.nanmin(all_xdata), np.nanmax(all_xdata)])
			ax[1].set_ylim([np.nanmin(all_ydata), np.nanmax(all_ydata)])
			
			#Calculate Linear Regression Models
			mask = (Cloud_SpaceCharge_All > np.percentile(Cloud_SpaceCharge_All, 0))
			Cloud_lm = sp.stats.linregress(Cloud_SignChange_All[mask], Cloud_SpaceCharge_All[mask])
			
			mask = (Air_SpaceCharge_All > np.percentile(Air_SpaceCharge_All, 0))
			Air_lm = sp.stats.linregress(Air_SignChange_All[mask], Air_SpaceCharge_All[mask])
			
			#Plot linear regression models
			ax[0].plot(np.sort(Air_SignChange_All, kind='mergesort'), np.sort(Air_SignChange_All, kind='mergesort')*Air_lm[0] + Air_lm[1], lw=0.5, color='black', linestyle='--')
			ax[1].plot(np.sort(Cloud_SignChange_All, kind='mergesort'), np.sort(Cloud_SignChange_All, kind='mergesort')*Cloud_lm[0] + Cloud_lm[1], lw=0.5, color='black', linestyle='--')

			#Annotate the scatter plot
			ax[1].annotate("Counts = %.0f\nR Value = %.4f" % (np.size(Cloud_SignChange_All), Cloud_lm[2]), xy=(1, 1), xycoords='axes fraction', xytext=(-20, -20), textcoords='offset pixels', horizontalalignment='right', verticalalignment='top', fontsize=10)
			ax[0].annotate("Counts = %.0f\nR Value = %.4f" % (np.size(Air_SignChange_All), Air_lm[2]), xy=(1, 1), xycoords='axes fraction', xytext=(-20, -20), textcoords='offset pixels', horizontalalignment='right', verticalalignment='top', fontsize=10)
			
			ax[0].annotate("(%s) %s" % (gu.alphabet[0], 
													  "Clear-Air"), 
													  xy=(0, 1), 
													  xycoords='axes fraction', 
													  xytext=(20, -20), 
													  textcoords='offset pixels', 
													  horizontalalignment='left', 
													  verticalalignment='top', 
													  fontsize=fontsize)
			ax[1].annotate("(%s) %s" % (gu.alphabet[1], 
													  "Cloud"), 
													  xy=(0, 1), 
													  xycoords='axes fraction', 
													  xytext=(20, -20), 
													  textcoords='offset pixels', 
													  horizontalalignment='left', 
													  verticalalignment='top', 
													  fontsize=fontsize)
			
			f.suptitle("Radiosonde Flight No.3,4,5,9,10 (IR-Identifier-80-20)", y=0.80)
			
			#Remove y axis on right-hand plot
			gu.hide_axis(ax=ax[1], x_or_y='y')
			
			#Set global properties after the plotting of data
			for subplot in ax: gu.fixed_aspect_ratio(ax=subplot, ratio=1, adjustable=None)

			#Save figure
			filename = self.Storage_Path + 'Plots/Hypothesis_3/SpaceCharge-Variability-PolarityChanges_Zhang-Identifier_All-Radiosondes.png'
			plt.savefig(filename, bbox_inches='tight', pad_inches=0.1, dpi=300)			
			
			############################################################################
			"""
			Plot the back-to-back histogram for time between polairty changes for both 
			clear-air and cloud regions.
			"""
			
			print("Mann-Whitney U-Test", sp.stats.mannwhitneyu(Air_SignChange_All, Cloud_SignChange_All, alternative='two-sided'))
			print("Wilcoxon signed-rank test", sp.stats.wilcoxon(Air_SignChange_All, np.random.choice(Cloud_SignChange_All, Air_SignChange_All.size)))
			
			# Plot Parameters
			data = [[Air_SignChange_All, Cloud_SignChange_All]]
			ylabel = [["Time between Polarity Changes (s)", "Time between Polarity Changes (s)"]]
			annotate = [["Clear-Air", "Cloud"]]
			name = [["Clear-Air", "Cloud"]]
			bins = [[30,30]]
			ylim = [[[0,50],[0,50]]]
			xscale = [['log', 'log']]
			yscale = [['linear', 'linear']]
			filename = self.Storage_Path + 'Plots/Hypothesis_3/Histogram_PolarityChanges_Zhang-Identifier_All-Radiosondes.png'
			
			# Call Back2Back_Histogram with plot parameters
			Back2Back_Histogram(
				data, 
				filename,
				bins,
				ylabel,
				annotate,
				ylim,
				xscale,
				yscale)
			
			############################################################################
			
			
	def Hypothesis4(self):
		"""
		HYPOTHESIS 4: Areas of turbulence increase the amount of 
		charge separation and act as a method to enhance the potential 
		gradient.
		"""
		
		return
	
	def RH_Comparison(self):
		"""This function will plot the relative humidity with respects to ice using various
		calculations of the saturated vapour pressure
		
		"""
		
		if self.verbose is True: gu.cprint("[INFO] You are running RH_Comparison from the DEV release", type='bold')
		
		############################################################################
		"""Prerequisites"""
		
		#Time Controls
		t_begin = time.time()
				
		############################################################################
		"""[Step 1] Calibrate bespoke sensors"""

		#Calibrate Height, Temperature and Convert PANDORA channels from counts to volts if required.
		Radiosonde_Cal = Radiosonde_Checks(self.Radiosonde_Data.copy(), None, self.sensor_package, self.height_range, check=1111)
		Radiosonde_Cal_Goff = Radiosonde_Checks(self.Radiosonde_Data.copy(), None, self.sensor_package, self.height_range, check=1111)
		Radiosonde_Cal_Buck = Radiosonde_Checks(self.Radiosonde_Data.copy(), None, self.sensor_package, self.height_range, check=1111)
		Radiosonde_Cal_Wexler = Radiosonde_Checks(self.Radiosonde_Data.copy(), None, self.sensor_package, self.height_range, check=1111)
		Radiosonde_Cal_Sonntag = Radiosonde_Checks(self.Radiosonde_Data.copy(), None, self.sensor_package, self.height_range, check=1111)
	
		#Calibrate Relative Humidity Sensor (e.g. find RH_ice)
		Radiosonde_Cal_Goff.RH(method='goff')
		Radiosonde_Cal_Buck.RH(method='arden-buck')
		Radiosonde_Cal_Wexler.RH(method='wexler')
		Radiosonde_Cal_Sonntag.RH(method='sonntag')
		
		#Return Data (make local to function only. i.e. DON'T use self.Radiosonde_Data)
		Radiosonde_Data = Radiosonde_Cal.finalise()
		Radiosonde_Data_Goff = Radiosonde_Cal_Goff.finalise()
		Radiosonde_Data_Buck = Radiosonde_Cal_Buck.finalise()
		Radiosonde_Data_Wexler = Radiosonde_Cal_Wexler.finalise()
		Radiosonde_Data_Sonntag = Radiosonde_Cal_Sonntag.finalise()
		
		############################################################################
		"""[Step 2] Plot radiosonde data"""
		
		Title = 'Radiosonde Flight No.' + str(self.sensor_package) + ' (' + self.Launch_Datetime.strftime("%d/%m/%Y %H%MUTC") + ')' if self.GPS_File is not None else 'Radiosonde Flight (N/A)'
		
		Height = Radiosonde_Data[:,1]
		Temperature = Radiosonde_Data[:,3]
		RH = Radiosonde_Data[:,4]
		
		#Plotting requirements
		plt.style.use('classic') #necessary if Matplotlib version is >= 2.0.0

		#Make sure we are creating new plot from scratch
		plt.clf()
		plt.close()
		
		#Define number of subplots sharing y axis
		f, ax1 = plt.subplots()

		ax1.minorticks_on()
		ax1.grid(which='major',axis='both',c='grey')

		#Rotate xticks in all subplots
		for tick in ax1.get_xticklabels(): tick.set_rotation(90)
		
		#Remove random junk from the plot
		f.subplots_adjust(hspace=0)
		plt.setp([a.get_yticklabels() for a in f.axes[1:]], visible=False)
		
		#Set axis parameters
		ax1.set_ylabel('Height $(km)$')
		ax1.set_ylim([np.nanmin(Radiosonde_Data[:,1]), np.nanmax(Radiosonde_Data[:,1])])
		
		#Define plot size
		f.set_size_inches(8, 8)
		
		#Plot RH
		ax1.plot(RH, Height, label='Original', lw=0.5)
		ax1.plot(Radiosonde_Data_Goff[:,-1], Radiosonde_Data_Goff[:,1], label='Goff-Gratch', lw=0.5)
		ax1.plot(Radiosonde_Data_Buck[:,-1], Radiosonde_Data_Buck[:,1], label='Arden-Buck', lw=0.5)
		ax1.plot(Radiosonde_Data_Wexler[:,-1], Radiosonde_Data_Wexler[:,1], label='Wexler', lw=0.5)
		ax1.plot(Radiosonde_Data_Sonntag[:,-1], Radiosonde_Data_Sonntag[:,1], label='Sonntag', lw=0.5)
		
		ax1.set_xlabel('RH $(\%)$')
		ax1.set_title(Title, fontsize=12)
		ax1.legend(loc='best')
		
		ax2 = ax1.twinx()

		ax2.plot(RH, Temperature, label='Original', lw=0.5, c='black')
		
		ax2.set_ylabel('Temperature ($^\circ$C)')
		
		ax2.set_ylim([np.nanmin(Temperature), np.nanmax(Temperature)])
		ax2.invert_yaxis()
		
		Freezing_Height = Height[gu.argnear(Temperature, 0)] if np.any(Temperature < 0) else -1
		print("Freezing_Height", Freezing_Height)
		ax1.axhline(y=Freezing_Height, c='black', ls='-', lw=1)
		
		############################################################################
		"""[Step 3] Save plot and return"""
		
		#Specify the directory the plots are stored in 
		path = os.path.dirname(self.Radiosonde_File).replace(self.Storage_Path + self.Processed_Data_Path,"")
		
		#Find any other plots stored in this directory
		previous_plots = glob.glob(self.Storage_Path + 'Plots/RH_Comparison/' + path + "/*")
		
		#Find the biggest 'v' number in plots
		plot_version = []
		for plots in previous_plots:
			try:
				plot_version.append(int(os.path.basename(plots)[34:37]))
			except ValueError:
				plot_version.append(int(os.path.basename(plots)[34:36]))
		
		plot_version = str(np.max(plot_version)+1) if len(plot_version) != 0 else '1'
		
		#Create full directory and file name
		Save_Location = self.Storage_Path + 'Plots/RH_Comparison/' + path + '/' + path + '_v' + plot_version.rjust(2,'0') + '_' + str(self.height_range[0]).rjust(2,'0') + 'km_to_' + str(self.height_range[1]).rjust(2,'0') + 'km.png'
		
		#Ensure the directory exists on file system and save to that location
		gu.ensure_dir(os.path.dirname(Save_Location))
		plt.savefig(Save_Location, bbox_inches='tight', pad_inches=0.1, dpi=300)
		
		############################################################################
		
		if self.verbose is True: print("[INFO] RH_Comparison completed successfully (In %.2fs)" % (time.time()-t_begin))

	def Ice_Concentration(self, Radiosonde_File=None, Calibrate=None, Height_Range=None, Sensor_Package=None):
		
		gu.cprint("[INFO] You are running Radiosonde_Ice_Concentration from the DEV release", type='bold')
		
		############################################################################
		"""Prerequisites"""
	   
		Storage_Path    		= '/storage/shared/glusterfs/phd/users/th863480/WC3_InSitu_Electrification/'
		Processed_Data_Path		= 'Processed_Data/Radiosonde/'
		Raw_Data_Path			= 'Raw_Data/'
		Plots_Path      		= 'Plots/Radiosonde/'
		
		t_begin = time.time()
		
		############################################################################
		"""[Step 1] Check and Import Data"""
		
		#Error check that either Radiosonde_File or Sensor_Package has been specified
		if Radiosonde_File is None and Sensor_Package is None: sys.exit("[Error] You must specify either the Radiosonde_File location or the Sensor_Package number")
		
		#Attempt to find the radiosonde file either directly or from glob
		Radiosonde_File = Storage_Path + Processed_Data_Path + Radiosonde_File if Radiosonde_File is not None else glob.glob(Storage_Path + Processed_Data_Path + 'Radiosonde_Flight_No.' + str(Sensor_Package).rjust(2,'0') + '_*/Radiosonde_Flight_PhD_James_No.' + str(Sensor_Package) + '*a.txt')
		
		#If no radiosonde file was found we end program
		if len(Radiosonde_File) == 0: sys.exit("[Error] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (Sensor_Package))
		
		#If the radiosonde file was found via glob we need to convert to str from list
		if isinstance(Radiosonde_File, list): Radiosonde_File = Radiosonde_File[0]
		
		#Import all the data
		if Radiosonde_File is not None: Radiosonde_Data = np.genfromtxt(Radiosonde_File, delimiter=None, skip_header=10, dtype=float, comments="#")
		
		Radiosonde_Cal = Radiosonde_Checks(Radiosonde_Data, Calibrate, Sensor_Package, Height_Range, check=1111)
		Radiosonde_Data = Radiosonde_Cal.return_data()
		
		Time = Radiosonde_Data[:,0][Radiosonde_Data[:,9] == 1112]
		PLL = Radiosonde_Data[:,7][Radiosonde_Data[:,9] == 1112]
		
		PLL[PLL == 0] = np.nan
		print(PLL)
		
		print(np.sum(np.isnan(PLL)))	
		
	def Lightning(self, Data, Radiosonde_File=None, Calibrate=None, Height_Range=None, Sensor_Package=None):
		"""Compares lightning data from ATDnet with the position of a radiosonde"""
		
		from matplotlib.ticker import MultipleLocator, FormatStrFormatter, MaxNLocator, LogLocator, ScalarFormatter
		from matplotlib.colors import LogNorm, ListedColormap
		from matplotlib.dates import DateFormatter, MinuteLocator, HourLocator, DayLocator
		
		gu.cprint("[INFO] You are running Radiosonde_Lightning from the STABLE release", type='bold')
		
		############################################################################
		"""Prerequisites"""
		
		#Time Controls
		t_begin = time.time()
			
		#Storage Locations
		Storage_Path    		= PhD_Global.Storage_Path_WC3
		Processed_Data_Path		= 'Processed_Data/Radiosonde/'
		Raw_Data_Path			= 'Raw_Data/'
		Plots_Path      		= 'Plots/Lightning/'
		
		#Plotting requirements
		plt.style.use('classic') #necessary if Matplotlib version is >= 2.0.0
		
		#Set-up data importer
		EPCC_Data = EPCC_Importer()
		
		#Time Offset
		time_offset = 20.5 #s
		
		############################################################################
		"""[Step 1] Check and Import Data"""
		
		t1 = time.time()
		
		#Error check that either Radiosonde_File or Sensor_Package has been specified
		if Radiosonde_File is None and Sensor_Package is None: sys.exit("[Error] You must specify either the Radiosonde_File location or the Sensor_Package number")
		
		#Attempt to find the radiosonde file either directly or from glob
		Radiosonde_File = Storage_Path + Processed_Data_Path + Radiosonde_File if Radiosonde_File is not None else glob.glob(Storage_Path + Processed_Data_Path + 'Radiosonde_Flight_No.' + str(Sensor_Package).rjust(2,'0') + '_*/Radiosonde_Flight_PhD_James_No.' + str(Sensor_Package) + '*a.txt')
		
		#If no radiosonde file was found we end program
		if len(Radiosonde_File) == 0: sys.exit("[Error] Radiosonde package No.%s does not exist. Has the radiosonde been launched yet or has the data been misplaced?" % (Sensor_Package))
		
		#If the radiosonde file was found via glob we need to convert to str from list
		if isinstance(Radiosonde_File, list): Radiosonde_File = Radiosonde_File[0]
		
		#Once the radiosonde file is found we can attempt to find the GPS file in the raw file section
		GPS_File = glob.glob(Storage_Path + Raw_Data_Path + 'Radiosonde_Flight_No.' + str(Sensor_Package).rjust(2,'0') + '_*/GPSDCC_RESULT*.tsv')
		
		#Import all the data
		if Radiosonde_File is not None: Radiosonde_Data = np.genfromtxt(Radiosonde_File, delimiter=None, skip_header=10, dtype=float, comments="#")
		
		#Get Launch Datetime
		Launch_Datetime, _ = Radiosonde_Launch(GPS_File, offset=time_offset)
		
		#Import ATDnet Data
		ID = np.where(Data['Date_ID'] == gu.toDateOnly(Launch_Datetime))[0][0]
		ATDnet_Time, ATDnet_LatLong = EPCC_Data.ATDnet(Data['ATDnet_File'][ID])
		
		if ATDnet_Time is None: raise IOError("No ATDnet data found for this Radiosonde flight")
		
		############################################################################
		"""[Step 2] Calibrate bespoke sensors"""
		
		t2 = time.time()
		
		#Calibrate Height, Temperature and Convert PANDORA channels from counts to volts if required.
		Radiosonde_Cal_Clean = Radiosonde_Checks(Radiosonde_Data.copy(), Calibrate, Sensor_Package, Height_Range, check=1111, enforce_parity=True)
		Radiosonde_Cal_Error = Radiosonde_Checks(Radiosonde_Data.copy(), Calibrate, Sensor_Package, Height_Range, check=1111, enforce_parity=False)
		
		#Return Data. _Clean : Enforce 1111/1112 parity, _Error: leave other parities alone. Used to identify link with lightning
		Radiosonde_Data_Clean = Radiosonde_Cal_Clean.return_data()
		Radiosonde_Data_Error = Radiosonde_Cal_Error.return_data()
		
		#Non 1111/1112 parity bits converted to nan (except time column)
		Radiosonde_Data_Error[~((Radiosonde_Data_Error[:,9] == 1111) ^ (Radiosonde_Data_Error[:,9] == 1112)),1:] = np.nan
		
		print("Launch_Datetime", Launch_Datetime)
		
		############################################################################
		"""[Step 3] Compare ATDnet with Radiosonde"""
		
		t3 = time.time()
		
		#First, convert Radiosonde time in flight to datetime64
		Radiosonde_Time = np.array(Launch_Datetime, dtype='datetime64[s]') + Radiosonde_Data_Clean[:,0].astype('timedelta64[s]')
		Radiosonde_LatLong = Radiosonde_Data_Clean[:,(11,10)]
		
		t4 = time.time()
		
		#Second, subset ATDnet for times when radiosonde was flying
		ATD_Mask = gu.bool2int((ATDnet_Time >= Radiosonde_Time[0]) & (ATDnet_Time <= Radiosonde_Time[-1]))
		ATDnet_Time = ATDnet_Time[ATD_Mask]
		ATDnet_LatLong = ATDnet_LatLong[ATD_Mask]
		
		#Third, join together the ATDnet timestamps and the Radiosonde timestamps
		mask = gu.mask(Radiosonde_Time, ATDnet_Time, approx=True)
		
		Radiosonde_Time = Radiosonde_Time[mask][0]
		Radiosonde_LatLong = Radiosonde_LatLong[mask][0]

		t5 = time.time()
		
		#Fourth, for each lightning detected, calculate the haversine between the latlong of the lightning and latlong of the radiosonde	
		Lightning_Distance = np.array([gu.haversine(tuple(atdnet_latlong), tuple(radiosonde_latlong))[0] for atdnet_latlong, radiosonde_latlong in zip(ATDnet_LatLong, Radiosonde_LatLong)], dtype=np.float64)

		#Fifth, remove nan values from array (N.B can't use gu.antinan as ATDnet has datetime64 which can't be handled)
		nan_mask = np.isnan(Lightning_Distance)
		ATDnet_Time = ATDnet_Time[~nan_mask]
		Lightning_Distance = Lightning_Distance[~nan_mask]
		
		############################################################################
		"""[Step 4]: Plot time series of lightning strikes"""
		
		Error_Mask = gu.contiguous(np.isnan(Radiosonde_Data_Error[:,5]), invalid=False)
		
		Error_Index = [[gu.bool2int(Error_Mask == val)[0], gu.bool2int(Error_Mask == val)[-1] + 0] for val in np.unique(Error_Mask)[1:]]
		Error_Length = np.diff(Error_Index).ravel()
		Radiosonde_Time_Error = np.array(Launch_Datetime, dtype='datetime64[s]') + Radiosonde_Data_Error[:,0].astype('timedelta64[s]')
			
		#Subset lightning distance to closest 100km strikes
		distance_mask = (Lightning_Distance/1000 < 100)
		ATDnet_Time = ATDnet_Time[distance_mask]
		Lightning_Distance = Lightning_Distance[distance_mask]/1000

		#Clear any previous plots
		gu.backend_changer('nbAgg')
		
		plt.clf()
		plt.close()
		
		#Plot lightning data as time-series
		plt.plot(ATDnet_Time, Lightning_Distance, 'p', ms=3, marker='o', markeredgecolor='None', markerfacecolor='blue', alpha=1, label="Lightning", zorder=4)
		
		plt.ylim([0,100])
		plt.grid(which='major',axis='both',c='grey', zorder=2)
		
		#Configure x axis ticks
		gu.date_ticks(plt.gca(), (ATDnet_Time[0], ATDnet_Time[-1]))
		
		#Write Plot Labels
		plt.ylabel("Distance from Radiosonde (km)")
		plt.title("Distance of Lightning Strikes from Radiosonde Flight No." + str(Sensor_Package))
		
		plt.annotate("$Counts$ = %.0f\n$Closest$ $Strike$ = %.2fkm" % (Lightning_Distance.size, np.nanmin(Lightning_Distance)), xy=(1, 1), xycoords='axes fraction', fontsize=12, xytext=(-5, -5), textcoords='offset points', ha='right', va='top')
		
		#Add fill_between highlighting when communication was lost with the Radiosonde
		cmap = plt.cm.Set2
		norm = plt.matplotlib.colors.Normalize(vmin=1, vmax=9)
		for i, (Error, Length) in enumerate(zip(Error_Index, Error_Length)): 
			plt.axvspan(Radiosonde_Time_Error[Error[0]], Radiosonde_Time_Error[Error[1]], alpha=0.5, color=cmap(norm(Length)), zorder=3)
			
		plt.tight_layout()
		
		#Create colour bar for the communication black-out time
		sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
		sm.set_array([])
		cb = plt.colorbar(sm, orientation='vertical', pad=0.01, ticks=[1,2,3,4,5,6,7,8,9])
		cb.set_label('Comms. Blackout ($s$)', labelpad=1, fontsize=10)
		cb.ax.set_xticklabels(['1', '2', '3', '4', '5', '6', '7', '8','9'])
		cb.ax.tick_params(labelsize=10)
		
		##SAVE PLOT###
		
		#Specify the directory the plots are stored in 
		path = os.path.dirname(Radiosonde_File).replace(Storage_Path + Processed_Data_Path,"")
		
		#Find any other plots stored in this directory
		previous_plots = glob.glob(Storage_Path + Plots_Path + path + "Timeseries/*")
		
		#Find the biggest 'v' number in plots
		plot_version = []
		for plots in previous_plots:
			try:
				plot_version.append(int(os.path.basename(plots)[34:37]))
			except ValueError:
				plot_version.append(int(os.path.basename(plots)[34:36]))
		
		plot_version = str(np.max(plot_version)+1) if len(plot_version) != 0 else '1'
		
		#Create full directory and file name
		Save_Location = Storage_Path + Plots_Path + path + '/Timeseries/' + path + '_v' + plot_version.rjust(2,'0') + '_LightningTimeseries.png'
		
		#Ensure the directory exists on file system and save to that location
		gu.ensure_dir(os.path.dirname(Save_Location))
		plt.savefig(Save_Location, bbox_inches='tight', pad_inches=0.1, dpi=300)
		
		print("Time series", Save_Location)
		
		############################################################################
		"""[Step 5] Plot lightning strikes and position of radiosonde on a map
		
		
		OPTIONS: USE THE fNorth AND fEast VALUES IN GPSDCC_RESULT TO CALCULATE THE 
		RADIOSONDE POSITION MORE ACCURATELY!"""
		
		from mpl_toolkits.basemap import Basemap
		
		from mpl_toolkits.axes_grid1.inset_locator import zoomed_inset_axes
		from mpl_toolkits.axes_grid1.inset_locator import inset_axes
		from matplotlib.patches import Polygon
		from matplotlib.dates import date2num, num2date
		from matplotlib.collections import LineCollection
		
		gu.backend_changer()
		
		#Provide dimensions of map
		lonW_Small = -2.0
		lonE_Small = 1.0
		latN_Small = 52.5
		latS_Small = 50.5

		lonW_Large = -11.0
		lonE_Large = 2.5
		latN_Large = 61.0
		latS_Large = 49.0
		
		#Map positioning
		Position = {'upper right' : (lonE_Small-0.55, latN_Small-0.15), 'upper left' : (lonW_Small+0.2, latN_Small-0.15),
			'lower right' : (lonE_Small-0.55, latS_Small+0.15), 'lower left' : (lonW_Small+0.2, latS_Small+0.15)}
		
		#Map Resolution
		map_res = 'f'
		
		#Create base map
		fig = plt.figure()
		ax = fig.add_subplot(111)

		map = Basemap(projection='merc',
			lat_0=51,
			lon_0=-3,
			resolution=map_res,
			llcrnrlon=lonW_Small,
			llcrnrlat=latS_Small,
			urcrnrlon=lonE_Small,
			urcrnrlat=latN_Small,
			ax=ax)
		
		#Define centre of map
		LatLong_Centre = [0.5*(latN_Small + latS_Small), 0.5*(lonE_Small + lonW_Small)]
		
		#Add overlays to map
		map.drawmapboundary(fill_color='LightBlue', zorder=0)
		map.fillcontinents(color='white', lake_color='LightBlue', zorder=0)
		map.drawcoastlines(color='DimGrey', linewidth=1, zorder=0)
		map.drawcountries(color='Grey', linewidth=1, zorder=0)
		map.drawmeridians(np.arange(-15, 5, 1),linewidth=0.5,color='DarkGrey',labels=[0,0,0,1], zorder=0)
		map.drawparallels(np.arange(-50, 70, 1),linewidth=0.5,color='DarkGrey',labels=[1,0,0,0], zorder=0)
		plt.title('Location of Lightning Strikes and Radiosonde Trajectory (Flight No.5)')

		city_labels = True
		if city_labels is True:
			
			# lat/lon coordinates to plot
			lats = [51.441314]
			lons = [-0.937447]
			
			# compute the native map projection coordinates
			x,y = map(lons,lats)
			
			map.scatter(x,y,s=30, edgecolors='DimGrey', marker='s', facecolors='none', alpha=1, zorder=5)
			
			label_txt = ['RUAO']
			
			for lab in range(0,np.size(x)): 
				plt.text(x[lab], y[lab], label_txt[lab], color='black', size=10,
					horizontalalignment='center', verticalalignment='top', zorder=6)
		
		#Create colour bar for plotting time progression
		Radiosonde_Time = date2num(Radiosonde_Time.astype(datetime))
		ATDnet_Time = date2num(ATDnet_Time.astype(datetime))
		
		#Configure colour-map setting
		cmap = plt.cm.rainbow
		norm = plt.matplotlib.colors.Normalize(vmin=Radiosonde_Time[0], vmax=Radiosonde_Time[-1])
		scalarMap = plt.cm.ScalarMappable(norm=norm, cmap='rainbow')	
		scalarMap.set_array([])
		
		print("Radiosonde_Time", Radiosonde_Time.dtype, Radiosonde_Time.shape, Radiosonde_Time.size)
		print("ATDnet_Time", ATDnet_Time.dtype, ATDnet_Time.shape, ATDnet_Time.size)
		
		#Add ATDnet Lightning Strikes
		x, y = map(ATDnet_LatLong[:,1], ATDnet_LatLong[:,0])
		map.scatter(x, y, s=5, marker='o', edgecolors='None', alpha=1, facecolor=cmap(norm(ATDnet_Time)))

		#Add Radiosonde Trajectory
		x, y = map(Radiosonde_LatLong[:,1], Radiosonde_LatLong[:,0])
		xy = np.vstack((x,y)).T
		for rad_time, start, stop in zip(Radiosonde_Time, xy[:-1], xy[1:]):
			xval, yval = zip(start, stop)
			map.plot(xval, yval, '-', lw=1, color=cmap(norm(rad_time)))
			
		#Add scale bar
		map.drawmapscale(*Position['lower right'],
			lat0=LatLong_Centre[0], lon0=LatLong_Centre[1], length=100, units='km', barstyle='fancy', ax=ax)
		
		#Create inset map axes
		axin = inset_axes(map.ax, width="30%", height="30%", loc=3)

		#Create inset map on the same Mercator Geographic Coordinate System
		omap = Basemap(projection='merc',
			lat_0=51,
			lon_0=-3,
			resolution=map_res,
			llcrnrlon=lonW_Large,
			llcrnrlat=latS_Large,
			urcrnrlon=lonE_Large,
			urcrnrlat=latN_Large,
			ax=axin)
			
		#Add overlays to map
		omap.drawmapboundary(fill_color='LightBlue')
		omap.fillcontinents(color='white',lake_color='LightBlue')
		omap.drawcoastlines(color='DimGrey', linewidth=.5)
		omap.drawcountries(color='Grey', linewidth=.5)
		
		#Add Zoomed Box
		bx, by = omap(map.boundarylons, map.boundarylats)
		xy = list(zip(bx,by))
		mapboundary = Polygon(xy,edgecolor='red',linewidth=2,fill=False)
		omap.ax.add_patch(mapboundary)
		
		#Create colour bar for the communication black-out time
		sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
		sm.set_array([])
		myFmt = plt.matplotlib.dates.DateFormatter('%H:%M')
		cb = plt.colorbar(sm, orientation='vertical', pad=0.01, label="Time (UTC)", format=myFmt, fraction=0.04)
		cb.ax.tick_params(labelsize=10)
		
		##SAVE PLOT###
		
		#Specify the directory the plots are stored in 
		path = os.path.dirname(Radiosonde_File).replace(Storage_Path + Processed_Data_Path,"")
		
		#Find any other plots stored in this directory
		previous_plots = glob.glob(Storage_Path + Plots_Path + path + "/Map/*")
		
		print("LOOKING", Storage_Path + Plots_Path + path + "/Map/")
		print("previous_plots", previous_plots)
		
		#Find the biggest 'v' number in plots
		plot_version = []
		for plots in previous_plots:
			try:
				plot_version.append(int(os.path.basename(plots)[34:37]))
			except ValueError:
				plot_version.append(int(os.path.basename(plots)[34:36]))
		
		plot_version = str(np.max(plot_version)+1) if len(plot_version) != 0 else '1'
		
		#Create full directory and file name
		Save_Location = Storage_Path + Plots_Path + path + '/Map/' + path + '_v' + plot_version.rjust(2,'0') + '_LightningMap.png'
		
		#Ensure the directory exists on file system and save to that location
		gu.ensure_dir(os.path.dirname(Save_Location))
		plt.savefig(Save_Location, bbox_inches='tight', pad_inches=0.1, dpi=300)
		
		print("Map", Save_Location)
		
		t6 = time.time()
		
		print("Time t2-t1 = %.2fs, t3-t2 = %.2fs, t4-t3 = %.2fs, t5-t4 = %.2fs, t6-t5 = %.2fs, Total = %.2fs" % 
			(t2-t1, t3-t2, t4-t3, t5-t4, t6-t5, t6-t1))
		
		print("[INFO] Radiosonde_Lightning completed successfully (In %.2fs)" % (time.time()-t_begin))	
		
		sys.exit()
		
if __name__ == "__main__":
	"""Launch the Radiosonde_Analysis.py from the command line. This python script gives command line
	options which can be found using Radiosonde_Analysis.py --help. An example input for a radiosonde
	flight is given as,
	
	>>> python Radiosonde_Analysis.py --sensor 3 --height 0.0 2.0 --calibrate count
	
	if using Radiosonde_ChargeCalibrator use:
	
	>>> python Radiosonde_Analysis.py --sensor x --height zmin zmax --calibrate volts
	
	where x is the radiosonde flight number, zmin and zmax are the height boundaries where you want to 
	perform the calibration and volts or units is required for calibrate to correctly get the linear
	current. Notes for zmin and zmax are to use an area of the ascent where both linear and log charge
	sensors did not saturate. Otherwise, the calibration will have a systematic bias.
	
	"""
	
	gu.cprint("Welcome to Radiosonde Analysis. Plotting the sounding data and calculating profile indices.", type='bold')
		
	############################################################################
	"""Process Command Line Arguments"""
	
	parser = argparse.ArgumentParser(description='Plot the radiosonde data for each flight during my PhD. The calibration from counts to voltage to quantity is applied automatically if found in Radiosonde_Calibration.py')
	
	#Command Line Arguments
	parser.add_argument('-v','--height',
		action="store", dest="height_range", nargs='+', type=float,
		help="Specify the minimum height used for plotting the radiosonde data. The format should be '-h 0 18' where 0 and 18 are the lower and upper bound heights respectively.", 
		default=(0,18), required=True)
	
	parser.add_argument('-s','--sensor',
		action="store", dest="sensor_package", type=int,
		help="Specify the radiosonde sensor package you want to plot. Ranges from 1+",
		default=1, required=True)

	parser.add_argument('-c', '--calibrate',
		action="store", dest="calibrate", type=str,
		help="Specify what level of calibration you want to apply to the research channels. Select either 'counts', 'volts', 'units' are available options",
		default='units', required=False)
	
	parser.add_argument('--tephigram',
		action='store_true', dest="plot_tephigram",
		help="Specify if you want to plot the tephigram of the specify radiosonde flight")
		
	parser.add_argument('--larkhill',
		action='store_true', dest="plot_larkhill",
		help="Specify if you want to plot the Larkhill Upper Level Sounding data on top of the radiosonde data")
	
	parser.add_argument('--reload',
		action='store_true', dest="reload",
		help="Specify if you want to reload the data processing of the chosen radiosonde flight.")
		
	parser.add_argument('--verbose',
		action='store_true', dest="verbose",
		help="Specify if you want output extra information about the data processing.")
		
	arg = parser.parse_args()
	arg.plot_tephigram = bool(arg.plot_tephigram)
	arg.plot_larkhill = bool(arg.plot_larkhill)
	
	if not np.any(np.in1d(arg.calibrate, ['volts', 'units', 'counts'])): sys.exit("[Error] Radiosonde_Analysis requires the Calibrate argument to be specified with either 'counts', 'volts' or 'units")
	
	#Convert Calibrate and Height_Range into tuples
	arg.height_range = tuple(arg.height_range)
	arg.calibrate = arg.calibrate.capitalize()

	#Initialise Clouds_ID, LayerType
	Clouds_ID = None
	LayerType = None
	
	############################################################################
	"""Start of Main Function"""
	
	tstart_main = time.time()
	
	gu.cprint("Everything was set-up correctly. Let crunch some numbers!", type='okblue')
	
	Data = PhD_Global.Data_CHIL

	
	Rad = Radiosonde(sensor_package=arg.sensor_package, height_range=arg.height_range, calibrate=arg.calibrate, reload=arg.reload, verbose=arg.verbose)
	Rad.Superplotter()
	Rad.Tephigram(plot_tephigram=arg.plot_tephigram, plot_larkhill=arg.plot_larkhill)
	
	
	#
	#Rad.Hypothesis2_v2()
	Rad.Hypothesis3()
	
	#print("FINISHED")
	sys.exit()
	
	
	
	
	
	
	
	
	Rad.RH_Comparison()
	sys.exit()
	
	#Identify the clouds within the radiosonde data
	Clouds_ID, LayerType = Radiosonde_CloudIdentifier(Height_Range=arg.Height_Range, Sensor_Package=arg.Sensor_Package)
	
	#Determine the charge calibration for the log sensor
	if np.any(np.in1d(arg.Calibrate, ['volts', 'units'])):
		Calibration_Log = Radiosonde_ChargeCalibrator(Calibrate=arg.Calibrate, Sensor_Package=arg.Sensor_Package)
	
	#Plot Radiosonde Data together in Cartesian Coordinates
	if np.any(np.in1d(arg.Calibrate, ['volts', 'units'])):
		Radiosonde_Superplotter(Calibrate=arg.Calibrate, Height_Range=arg.Height_Range, Sensor_Package=arg.Sensor_Package, Clouds_ID=Clouds_ID, LayerType=LayerType, Calibration_Log=Calibration_Log)
	else:
		Radiosonde_Superplotter(Calibrate=arg.Calibrate, Height_Range=arg.Height_Range, Sensor_Package=arg.Sensor_Package, Clouds_ID=Clouds_ID, LayerType=LayerType)
	sys.exit()
	
	
	#Plot Radiosonde Data together in Tephigram Coordinates
	Radiosonde_Tephigram(Height_Range=arg.Height_Range, Sensor_Package=arg.Sensor_Package, plot_tephigram=arg.plot_tephigram, plot_larkhill=arg.plot_larkhill)
	
	#Plot Lightning maps and comparison with Radiosonde Trajectory
	Radiosonde_Lightning(Data, Calibrate=arg.Calibrate, Height_Range=arg.Height_Range, Sensor_Package=arg.Sensor_Package)
	
	#IN THE FUTURE:
	#Radiosonde_ChargeCalibrator(Calibrate=arg.Calibrate, Height_Range=arg.Height_Range, Sensor_Package=arg.Sensor_Package)
	#Radiosonde_Ice_Concentration(Calibrate=arg.Calibrate, Height_Range=arg.Height_Range, Sensor_Package=arg.Sensor_Package)
	
	gu.cprint("[Radiosonde_Analysis]: All Tasks Completed, Time Taken (s): %.0f" % (time.time()-tstart_main), type='okgreen')