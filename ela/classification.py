from __future__ import print_function # anything else?

import sys
import pandas as pd
import numpy as np
from sklearn import neighbors

import geopandas as gpd

from ela.textproc import EASTING_COL, NORTHING_COL, DEPTH_FROM_AHD_COL, DEPTH_FROM_COL, DEPTH_TO_AHD_COL, DEPTH_TO_COL, PRIMARY_LITHO_COL, PRIMARY_LITHO_NUM_COL, GEOMETRY_COL
from ela.spatial import *

KNN_WEIGHTING = 'distance'
# 0=sand
# 1=sandstone 
# 2=clay
# 3=limestone
# 4=shale
# 5=basalt
# 6=coffee rock
LITHOLOGIES = ['sand','sandstone','clay','limestone','shale','basalt','coffee']


def to_litho_class_num(lithology, kv):
    if lithology in kv.keys():
        return kv[lithology]
    else:
        return np.nan

def v_to_litho_class_num(lithologies, kv):
    return np.array([to_litho_class_num(x, kv) for x in lithologies])

def create_numeric_classes(my_lithologies):
    my_lithologies_numclasses = dict([(my_lithologies[i], i) for i in range(len(my_lithologies))])
    return my_lithologies_numclasses


def lithologydata_slice_depth(df, slice_depth):
    '''
    Subset data frame with entries at a specified AHD coordinate

    :df: bore lithology data  
    :type: pandas data frame 
    
    :slice_depth: AHD coordinate at which to slice the data frame for lithology observations 
    :type: double  
    
    :return: a subset of the input data frame, entries intersecting with the specified slice depth
    :rtype: a (view of a) data frame

    '''
    df_slice=df.loc[(df[DEPTH_FROM_AHD_COL] >= slice_depth) & (df[DEPTH_TO_AHD_COL] <= slice_depth)]
    return df_slice

def get_lithology_observations_for_depth(df, slice_depth, lithology_column_name = PRIMARY_LITHO_COL):
    '''
    Subset data frame with entries at a specified AHD coordinate, and with valid lithology information.

    :df: bore lithology data  
    :type: pandas data frame 
    
    :slice_depth: AHD coordinate at which to slice the data frame for lithology observations 
    :type: double 

    :lithology_column_name: name of the column with string information to use to strip entries with missing lithology information
    :type: string 
    
    :return: a subset of the input data frame, entries intersecting with the specified slice depth
    :rtype: a (view of a) data frame
    '''
    df_slice=lithologydata_slice_depth(df, slice_depth)
    df_1=df_slice[df_slice[lithology_column_name] != ""]
    return df_1


def extract_bore_primary_litho_class_num(bore_log_df):
    '''
    Gets the columns easting, northing, primary lithology class number, AHD depth 'from' and 'to' from a bore data log
    '''
    xx = bore_log_df[EASTING_COL].values
    yy = bore_log_df[NORTHING_COL].values
    ss = bore_log_df[PRIMARY_LITHO_NUM_COL].values
    zz_from = bore_log_df[DEPTH_FROM_AHD_COL].values
    zz_to = bore_log_df[DEPTH_TO_AHD_COL].values
    return xx, yy, zz_from, zz_to, ss

def make_training_set(observations):
    X = observations.as_matrix(columns=[EASTING_COL, NORTHING_COL])
    y = np.array(observations[PRIMARY_LITHO_NUM_COL])
    return (X, y)

def get_knn_model(df, slice_depth, n_neighbours):
    df_1 = get_lithology_observations_for_depth(df, slice_depth)
    X, y = make_training_set(df_1)
    if n_neighbours > len(df_1):
        return None
    else:
        knn = neighbors.KNeighborsClassifier(n_neighbours, weights = KNN_WEIGHTING).fit(X, y)
        return knn

def interpolate_over_meshgrid(predicting_algorithm, mesh_grid):
    '''
    Interpolate lithology data

    :predicting_algorithm: algorithm such as KNN
    :type: algorithm with a predict method.
        
    :mesh_grid: coordinate matrices to interpolate over (numpy.meshgrid)
    :type: tuple
    
    :return: predicted values over the grid
    :rtype: numpy array

    '''
    xx, yy = mesh_grid
    if predicting_algorithm is None:
        # the training set was too small and prediction cannot be made (odd that scikit would have let us train still)
        predicted = np.empty(xx.shape)
        predicted[:] = np.nan # np.empty should have done that already, but, no...
    else:
        predicted = predicting_algorithm.predict(np.c_[xx.ravel(), yy.ravel()])
        predicted = predicted.reshape(xx.shape)
    return predicted

def interpolate_lithologydata_slice_depth(df, slice_depth, n_neighbours, mesh_grid):
    '''
    Interpolate lithology data

    :df: bore lithology data  
    :type: pandas data frame 
    
    :slice_depth: AHD coordinate at which to slice the data frame for lithology observations 
    :type: double  
    
    :n_neighbours: Number of neighbors to pass to KNeighborsClassifier
    :type: integer
    
    :mesh_grid: coordinate matrices to interpolate over (numpy.meshgrid)
    :type: tuple
    
    :return: predicted values over the grid
    :rtype: numpy array

    '''
    knn = get_knn_model(df, slice_depth, n_neighbours)
    return interpolate_over_meshgrid(knn, mesh_grid)

def interpolate_lithologydata_slice_depth_bbox(df, slice_depth, n_neighbours, geo_pd, grid_res = 100):
    '''
    Interpolate lithology data

    :df: bore lithology data  
    :type: pandas data frame 
    
    :slice_depth: AHD coordinate at which to slice the data frame for lithology observations 
    :type: double  
    
    :n_neighbours: Number of neighbors to pass to KNeighborsClassifier
    :type: integer
    
    :geo_pd: vector spatial data to get bounds of interest (box)
    :type: 
    
    :grid_res: grid resolution in m for x and y.
    :type: integer
    
    :return: predicted values over the grid
    :rtype: numpy array

    '''
    mesh_grid = create_meshgrid(geo_pd, grid_res)
    return interpolate_lithologydata_slice_depth(df, slice_depth, n_neighbours, mesh_grid)


def class_probability_estimates_depth(df, slice_depth, n_neighbours, mesh_grid, func_training_set=None):
    df_1 = get_lithology_observations_for_depth(df, slice_depth)
    X, y = make_training_set(df_1)
    if not (func_training_set is None):
        X, y = func_training_set(X, y)
    knn = neighbors.KNeighborsClassifier(n_neighbours, weights = KNN_WEIGHTING).fit(X, y)
    xx, yy = mesh_grid
    class_prob = knn.predict_proba(np.c_[xx.ravel(), yy.ravel()])
    n_classes = class_prob.shape[1]
    probs = []
    for i in range(n_classes):
        p = class_prob[:,i].reshape(xx.shape)
        probs.append(p)
    return probs

def class_probability_estimates_depth_bbox(df, slice_depth, n_neighbours, geo_pd, grid_res = 100, func_training_set=None):
    xx, yy = create_meshgrid(geo_pd, grid_res)
    return class_probability_estimates_depth(df, slice_depth, n_neighbours, mesh_grid, func_training_set)

def interpolate_volume(volume, df, z_ahd_coords, n_neighbours, mesh_grid):
    dim_x,dim_y = mesh_grid[0].shape
    dim_z = len(z_ahd_coords)
    if volume.shape[0] != dim_x or volume.shape[1] != dim_y or volume.shape[2] != dim_z:
        raise Error("Incompatible dimensions in arguments")
    for index,ahd_height in enumerate(z_ahd_coords):
        surface = interpolate_lithologydata_slice_depth(df, ahd_height, n_neighbours, mesh_grid)
        volume[:,:,index]=surface


def pad_training_set_functor(classes):
    ### NEED TO APPEND DUMMY DATA TO MAKE SURE ALL CLASSES ARE PRESENT IN EACH SLICE ###
    # 0=sand
    # 1=sandstone 
    # 2=clay
    # 3=limestone
    # 4=shale
    # 5=basalt
    # 6=coffee rock
    n = len(classes)
    def pad_training_set(X, y):
        dummy_EN=np.array([[0,0] for i in range(n)])
        dummy_targets=np.array(range(n))
        X=np.vstack((X,dummy_EN))
        y=np.append(y,dummy_targets)
        return (X, y)
    return pad_training_set



def get_lithology_classes_probabilities(lithologies, shape, df, z_ahd_coords, n_neighbours, mesh_grid):
    dim_x,dim_y,dim_z = shape
    vol_template=np.empty((dim_x,dim_y,dim_z))
    classprob_3d_arrays=[vol_template.copy() for i in lithologies]
    n_classes = len(lithologies)
    pad_training_set = pad_training_set_functor(lithologies)
    # iterate over all slices
    for z_index,ahd_height in enumerate(z_ahd_coords):
        result=class_probability_estimates_depth(df, ahd_height, n_neighbours, mesh_grid, func_training_set = pad_training_set)
        for i in range(n_classes):
            classprob_3d_arrays[i][:,:,z_index]=result[i]
    return classprob_3d_arrays


def extract_single_lithology_class_3d(lithology_3d_classes, class_value):
    single_litho = np.copy(lithology_3d_classes)
    other_value = class_value-1.0
    single_litho[(single_litho != class_value)] = other_value
    # We burn the edges of the volume, as I suspect this is necessary to have a more intuitive viz (otherwuse non closed volumes)
    single_litho[0,:,:] = other_value
    single_litho[-1,:,:] = other_value
    single_litho[:,0,:] = other_value
    single_litho[:,-1,:] = other_value
    single_litho[:,:,0] = other_value
    single_litho[:,:,-1] = other_value
    return single_litho