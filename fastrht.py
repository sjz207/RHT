#!/usr/bin/python

# FAST ROLLING HOUGH TRANSFORM

# wlen : Diameter of a 'window' - the data to be evaluated at one time
# frac : fraction (percent) of one angle that must be 'lit up' to be counted
# smr  : smoothing radius of unsharp mask function.
# ulen : length of unsharp mask square. Must be at least wlen + smr/2

# ---------------------------------------------------------------------------------------------------
from __future__ import division
import numpy as np
import math
import time
import random
from astropy import wcs
from astropy.io import fits
import scipy as sp
from scipy.ndimage import filters, imread
import copy

TEXTWIDTH = 40

def getData(filename):
    #This could replace the specialized code above if I'm using simple images
    if filename.endswith('.fits'):
	    hdulist = fits.open(filename) #Opens HDU list
	    gassslice = hdulist[0].data #Reads all data as an array
    else:
		gassslice = imread(filename, True) #Makes B/W array
    x, y = gassslice.shape #Gets dimensions
    return gassslice, x, y

def setParams(gassslice, w, s, f, gass=False):
    wlen = w #101.0 #Window diameter
    frac = f #0.70 #Theta-power threshold to store
    smr = s #11.0 #Smoothing radius

    ulen = np.ceil(wlen + smr/2) #Must be odd
    if np.mod(ulen, 2) == 0:
        ulen += 1
    ucntr = np.floor(ulen/2)

    wcntr = np.floor(wlen/2)
    ntheta = math.ceil((np.pi*np.sqrt(2)*((wlen-1)/2.0)))  

    
    dtheta = np.pi/ntheta
    theta = np.arange(0, np.pi, dtheta)
    
    wsquare1 = np.ones((wlen, wlen), np.int_)
    kernel = circ_kern(wsquare1, smr) 
    wkernel = circ_kern(wsquare1, wlen) 
    
    if gass==True:
        mask = makemask(wkernel, gassslice)
    else:
        mask = None #Default is no mask

       # xyt = np.load('xyt2_101_223.npy')
       # mask = np.load('w101_mask.npy')

    return wlen, frac, smr, ucntr, wcntr, ntheta, dtheta, theta, mask


#Performs a circle-cut of given radius on inkernel.
#Outkernel is 0 anywhere outside the window.    
def circ_kern(inkernel, radius):
    #These are all the possible (m,n) indices in the image space, centered on center pixel
    mnvals = np.indices((len(inkernel), len(inkernel)))
    kcntr = np.floor(len(inkernel)/2.0)
    mvals = mnvals[:,:][0] - kcntr
    nvals = mnvals[:,:][1] - kcntr

    rads = np.sqrt(nvals**2 + mvals**2)
    outkernel = copy.copy(inkernel)
    outkernel[rads > radius/2] = 0
    
    return outkernel

'''
I was playing with this in the scrap.py file and think I get it better now.
#import scrap
#print scrap.ring(20, 6, 12) 
'''

#Unsharp mask. Returns binary data.
def umask(data, inkernel):    
    outdata = filters.correlate(data, weights=inkernel)
    
    #I don't understand what kernweight does..
    #Our convolution has scaled outdata by sum(kernel), so we will divide out these weights.
    kernweight = np.sum(inkernel, axis=0)
    kernweight = np.sum(kernweight, axis=0)
    subtr_data = data - outdata/kernweight
    
    #Convert to binary data
    bindata = copy.copy(subtr_data)
    bindata[subtr_data > 0] = 1
    bindata[subtr_data <= 0] = 0

    return bindata

def fast_hough(in_arr, xyt, ntheta):
    incube = np.repeat(in_arr[:,:,np.newaxis], repeats=ntheta, axis=2)
    out = np.sum(np.sum(incube*xyt,axis=0), axis=0)
    
    return out        


#------------------------------ Got it >
def all_thetas(window, thetbins):
    wx, wy = window.shape #Parse x/y dimensions
    ntheta = len(thetbins) #Parse height in theta
    
    #Makes prism; output has dimensions (x, y, theta)
    out = np.zeros((wx, wy, ntheta), np.int_)
    
    for i in xrange(wx):
        for j in xrange(wy):
            #At each x/y value, create new single-pixel image
            w_1 = np.zeros((wx, wy), np.float_)
            
            # run the Hough for each point one at a time
            if window[i,j] == 1:
                w_1[i,j] = 1
       
                H, thets, dist = houghnew(w_1, thetbins) 
                rel = H[np.floor(len(dist)/2), :]
                out[i, j, :] = rel
      
    return out    

def houghnew(img, theta=None, idl=False):
    if img.ndim != 2:
        raise ValueError('The input image must be 2-D')

    if theta is None:
        theta = np.linspace(-np.pi / 2, np.pi / 2, 180)
    
    wx, wy = img.shape    
    wmid = np.floor(wx/2)
    
    if idl == True:
        print 'idl values'
        #Here's that ntheta again..
        ntheta = math.ceil((np.pi*np.sqrt(2)*((wx-1)/2.0)))  
        theta = np.arange(0, np.pi, np.pi/ntheta)
        dtheta = np.pi/ntheta

    # compute the vertical bins (the distances)
    d = np.ceil(np.hypot(*img.shape))
    nr_bins = d
    bins = np.linspace(-d/2, d/2, nr_bins)

    # allocate the output image
    out = np.zeros((nr_bins, len(theta)), dtype=np.uint64)

    # precompute the sin and cos of the angles
    cos_theta = np.cos(theta)
    sin_theta = np.sin(theta)

    # find the indices of the non-zero values in
    # the input image
    y, x = np.nonzero(img)

    # x and y can be large, so we can't just broadcast to 2D
    # arrays as we may run out of memory. Instead we process
    # one vertical slice at a time.
    for i, (cT, sT) in enumerate(zip(cos_theta, sin_theta)):

        # compute the base distances
        distances = (x - wmid) * cT + (y - wmid) * sT

        # round the distances to the nearest integer
        # and shift them to a nonzero bin
        shifted = np.round(distances) - bins[0]

        # cast the shifted values to ints to use as indices
        indices = shifted.astype(np.int)

        # use bin count to accumulate the coefficients
        bincount = np.bincount(indices)

        # finally assign the proper values to the out array
        out[:len(bincount), i] = bincount

    return out, theta, bins

def window_step(data, wlen, frac, smr, ucntr, wcntr, theta, ntheta, mask): 
    #Create progress meter
    OLDP = 0
    def update_progress(progress):
        if progress > 0.0 and progress <= 1.0:
            p = int(TEXTWIDTH*progress/1.0) 
            if p > OLDP:
                print '\r3/3.. [{0}{1}]%'.format('#'*p, ' '*(TEXTWIDTH-p))
        elif progress > 0.0 and progress <= 100.0:
            p = int(TEXTWIDTH*progress/100.0) 
            if p > OLDP:
                print '\r3/3.. [{0}{1}]%'.format('#'*p, ' '*(TEXTWIDTH-p)) 
        elif progress == 0.0:
            print '\r3/3.. [{0}]%'.format(' '*TEXTWIDTH)
                    

    update_progress(0.0)
    
    #Circular kernels
    wsquare1 = np.ones((wlen, wlen), np.int_) #Square of 1s
    kernel = circ_kern(wsquare1, smr) #Stores an smr-sized circle
    wkernel = circ_kern(wsquare1, wlen) #And an wlen-sized circle
    xyt = all_thetas(wkernel, theta) #Cylinder of all theta values per point
    print xyt.shape, 'xyt shape' #TODO

    #unsharp mask the whole data set
    udata = umask(data, kernel)
    
    #Hough transform of same-sized circular window of 1's
    h1 = fast_hough(wkernel, xyt, ntheta)

    start = time.clock()
    Hthets = []
    Hi = []
    Hj = []
    
    start0=time.clock()
    dcube = np.repeat(udata[:,:,np.newaxis], repeats=ntheta, axis=2)
    end0 = time.clock()
    print 'cube data', end0-start0 #TODO
    

    htapp = Hthets.append
    hiapp = Hi.append
    hjapp = Hj.append
    npsum = np.sum

    #Loop: (j,i) are centerpoints of data window.
    datax, datay = data.shape
    for j in xrange(datay):        

        update_progress(j/datay) #For monitoring progress TODO
        if j >= ucntr and j < (datay - ucntr):
            for i in xrange(datax):
                
                if i >= ucntr and i < (datax - ucntr):
                    
                    wcube = dcube[j-wcntr:j+wcntr+1, i-wcntr:i+wcntr+1,:]   
                    
                    h = npsum(npsum(wcube*xyt,axis=0), axis=0)
                    
                    hout = h/h1 - frac
                    hout[hout<0.0] = 0.0
                
                    if np.sum(hout) > 0:
                        htapp(hout)
                        hiapp(i)
                        hjapp(j)
        
    end = time.clock()
    print 'Code time %.6f seconds' % (end - start)         
    
    return Hthets, Hi, Hj

#*********************************************************

def main(filepath=None, silent=False):
    print '*'*TEXTWIDTH
    print 'Fast Rolling Hough Transform by Susan Clark'
    print '*'*TEXTWIDTH
    if filepath==None:
		filepath = raw_input('Please enter the full relative path of a file to analyze:')
	
    print '1/3.. Loading Data'
    xy_array, datay, datax = getData(filepath)
    print '1/3.. Successfully Loaded Data!'

    filename = filepath.split(".")[0] #Works if there are no other '.' besides at file extension
    print '1/3:: Analyzing', filename, str(datax), 'x', str(datay)

    print '2/3.. Setting Params'
    #TODO wrap parameter input
    wlen, frac, smr, ucntr, wcntr, ntheta, dtheta, theta, mask = setParams(xy_array, 125, 5, 0.70)
    print '2/3.. Successfully Set Params!'
    print '2/3:: ' #TODO Summary of Params

    print '3/3.. Runnigh Hough Transform'
    hi_filename = filename + '_hi.npy'
    hj_filename = filename + '_hj.npy'
    hthets_filename = filename + '_hthets.npy'
    print '3/3.. Your Data Will Be Saved As:', hi_filename, hj_filename, hthets_filename 
	
    Hthets, Hi, Hj = window_step(xy_array, wlen, frac, smr, ucntr, wcntr, theta, ntheta, mask) #TODO progress meter
    hi = np.array(Hi)
    hj = np.array(Hj)
    hthets = np.array(Hthets)
    np.save(hi_filename, hi)
    np.save(hj_filename, hj)
    np.save(hthets_filename, hthets)
    print '3/3:: Successfully Saved Data!'

def interpret(filepath=None, interactive=False):
    '''
    Using name_hi.npy, name_hj.npy, name_hthets.npy,
    Prodces:
        Backprojection --> name_backproj.npy
        Backprojection Overlayed on Image --> name_overlay.npy 
        ThetaSpectrum --> name_spectrum.npy
    '''

    if !interactive:
        try:
            filename = filepath.split(".")[0]
            hi_filename = filename + '_hi.npy'
            hj_filename = filename + '_hj.npy'
            hthets_filename = filename + '_hthets.npy'
            import numpy as np
            hi = np.load(hi_filename)
            hj = np.load(hj_filename)
            hthets = np.load(hthets_filename)
            
            #Backprojection *Minimum XY Size, coords offset by low*
            low = (min(hi), min(hj))
            high = (max(hi), max(hj))
            small_tflat_xy = np.zeros(np.add(np.subtract(high, low), (1, 1)))
            coords = np.subtract(zip(hi, hj), low)
            for c in coords:
                small_tflat_xy[c[0]][c[1]] = sum(hthets[coords.index(c)])
            backproj_filename = filename + '_backproj.npy'
            np.save(backproj_filename, small_tflat_xy)

            #Overlay *Image coords*
            image, imx, imy = getData(filepath)
            #np.divide(image, np.amax(image)) #TODO: Image Weighting to 1?
            large_tflat_xy = np.zeros_like(image)
            small_shape = small_tflat_xy.shape
            for a in small_shape[0]:
                for b in small_shape[1]:
                    large_tflat_xy[a+low[0]][b+low[1]] = small_tflat_xy[a][b]
            weight = 1.0 #TODO: Weight by powers of large_tflat_xy
            overlay = np.multiply(image, np.multiply(large_tflat_xy, weight))
            overlay_filename = filename + '_overlay.npy'
            np.save(overlay_filename, overlay)

            #Spectrum *Length ntheta array of theta power for whole image*
            spectrum = [sum(theta) for theta in zip(hthets)]
            spectrum_filename = filename + '_overlay.npy'
            np.save(spectrum_filename, spectrum)


        except Exception:
            pass #Silent, fast failure
    else:   
        print '*'*TEXTWIDTH
        print 'Rolling Hough Transform Interpreter by Lowell Schudel'
        print '*'*TEXTWIDTH
        
        '''
        Input Handling

        Failures:
        0- Bad filepath
            0.1-
        1- Output files not found
            1.1- Did not choose to reananlyze
            1.2- Generated output files, reinterpreted
            1.3- Failed to find image file
        2- Data reading failure
            2.1

        Exits:
        0- No image filepath entered
        1- Outputs not found, no new analysis
        '''
        from os.path import isfile
        #Filename Assignment
        if filepath==None:
            try:
                filepath = raw_input('Please enter the relative path of a file to analyze:')         
            except EOFError:
                exit('Exiting interpret: 0') #Exit 0
            
        try:
            filename = filepath.split(".")[0]
        except IndexError:
            print 'Filename does not appear to have an extension'
        hi_filename = filename + '_hi.npy'
        hj_filename = filename + '_hj.npy'
        hthets_filename = filename + '_hthets.npy'
        
        
        
        if !(isfile(hi_filename) and isfile(hj_filename) and isfile(hthets_filename)): 
            print 'Output files for this image were not found.'
            from distutils.util import strtobool
            try:
                reanalyze = strtobool(raw_input('Would you like to reanalyze the image? y/[n]'))
            except ValueError:
                #No choice
                reanalyze = False #Failure 1.1 
            except EOFError:
                #Default choice
                realanyze = False 

            if realanyze 
                if isfile(filepath):
                    main(filepath, silent=True)
                    print 'File analyzed successfully. Reinterpreting...' #Failure 1.2
                    interpret(filepath)
                else:
                    print 'Nonexistant image file, please try another.' #Failure 1.3
            else:
                exit('Exiting interpret: 1') #Exit 1

        else: 
            from numpy import load
            try:
                hi = np.load(hi_filename)
                hj = np.load(hj_filename)
                hthets = np.load(hthets_filename)
            except IOError: 
                print 'One or more output files are invalid' #Failure 2.1


