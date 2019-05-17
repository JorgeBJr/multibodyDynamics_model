
# coding: utf-8

#     4/4/17- Setting up my model (Model 1) in MATLAB using ode45
#     Models 2-7 since then (and even more errors/fixes)
#     Model 8 was essentially refined on 6/29/17
#     7/6/17- Model 9 development will incorporate our cost function and 
#         multiple wing strokes.
#     8/7/17- Model 10(a?) will do all of the above for SEVERAL full run 
#         throughs. Model 10(b?) will have a Gaussian cost function. 
#             a.k.a. no more window!
#     9/4/17- FIXED K and c
#     9/6/17- Fixed tau to have a maximum value of 10000 g*(cm^2)/(s^2)
#     2/8/18- Eliminated the need for global variables and implemented 
#         %structs that are passed into the ODE.
#     3/6/18- Model 11 is born.
#         Restructured the ENTIRE layout of the variables to have nested
#         structs which contain what we want.
#         hws contains a 2500x1 struct of: 
#             ICs, F, alpha, tau, Q, cost, NewICs
#         Each hws is nested in a 100x1 large struct for Qstore and Winstore
#     7/3/18- Fixed a MAJOR error in the resting angle of the torsional spring.
#         Now there is the appropriate restorative force.
#     7/18/18- Model 12 was born.
#         Fixed another MAJOR error. tau_abdo is now a fixed force (as
#         originally intended), needed to fix myODE and remove the
#         sinusoidal component of the applied torque.
#     ~8/17/18- Incorporated LengthScaleFactor to change the size of the model.
#     10/16/18- Incorporated Size
#     1/7/19- Finally attempting a formal Model Predictive Control (MPC)
#     1/31/19- Corrected issues pertaining to the Moment of Inertia.
#         myODE5 was born.
#         1) incorrect multiplication in myODE4,
#         2) accounting for parallel axis theorem (due to petiole length
#         extension) in myODE4.
#     2/14/19- For the sake of efficiency, lines 184, and 314 were muted
#         to no longer create the Qstore struct. 
# ** Conversion to Python **
#     2/25/19- Code being migrated to Python. This transition will switch to 
#         fixed time steps. This transition will likely lead to the use of a 
#         GPU or Amazon Web Services. 
#     4/8/19- Added wing torque term as a fourth control parameter (tau_w) to 
#         add the option of making the model fully actuated. I have also saved
#         the output of this file to be pre_Winstore. A MATLAB script will 
#         convert this file into the structure I desire in MATLAB. 
#         Single core processing.
#     4/11/19- Created multi-core verson of the code. This uses the @jit
#         decorator in the numba package to use multi-processing.
#     5/1/19- Went back to global variables (I know, it's not the best 
#         practice, but I have no patience at this time).
# 
#     12b is for horizontal aggressive maneuver
#     12c is for vertical aggressive maneuver
#     12h is for sum of prime number sines

# %% The python preamble
## We the People, in Order to form a perfect Union,...
#import matplotlib.pyplot as plt
import numpy as np
#import os
#import pandas as pd
#import seaborn as sns
from scipy.integrate import odeint
from scipy.io import savemat #This is imported to save .mat files
#import random
import time
from datetime import datetime
import sys
import multiprocessing 
#from multiprocessing import Pool, cpu_count
import importlib
import functools
import multibodyDynamics_12h #Note: that this is a custom-written file which
               #contains the ODEs to run the code.
from collections import OrderedDict

sys_version = sys.version; #The system version for troubleshooting
print(sys_version)

tstamp_start = datetime.now()
print(tstamp_start)

#import importlib

#Packages originally included here which I have muted out.
#matplotlib inline
# from matplotlib import cm
# from matplotlib import pyplot as plt
# from pylab import plot,xlabel,ylabel,title,legend,figure,subplots
# import seaborn as sb
# import matplotlib.pylab as pylab
    #forces plots to appear in the ipython notebook

# %% Variables to alter (if someone else is making changes for me)
#Note: all numerical values MUST be integers

numOfTrajectories = int(3); #Number of trajectories per half wing stroke spray
shift = int(0); #This is to increase the file number as appropriate
FullRuns = int(1); #Number of full runs
treatment = 'fa'; #Fully-actuated (fa), Under-actuated (ua), 
                  #Under-actuated AND shifted (us)

# %% Variable setup 
#(note, all are scalar values)

LengthScaleFactor = 1; #This will multiply all linear scales of the model
    #appropriately to modify the size of the model.
LengthExtend = 0; #This will lengthen the difference between the two masses.

L1 = LengthScaleFactor*0.908; #Length from the thorax-abdomen joint to 
    #the center of the head-thorax mass in cm.
L3 = LengthScaleFactor*0.75; #Length from the thorax-abdomen joint to the 
    #aerodynamic force vector in cm
# #If we do not want the L3 off the m1 center of mass:
# L3 = L1; #Length from the thorax-abdomen joint to the 
#     #aerodynamic force vector in cm
ahead = LengthScaleFactor*0.908; #Major axis of the head-thorax ellipsoid
    #in cm.
abutt = LengthScaleFactor*1.7475; #Major axis of the abdomen ellipsoid
    #in cm.
bhead = LengthScaleFactor*0.507; #Minor axis of the head-thorax ellipsoid
    #in cm.
bbutt = LengthScaleFactor*0.1295; #Minor axis of the abdomen ellipsoid
    #in cm.

L_petiole = LengthExtend*(2*(ahead+abutt)); #Length of petiole extension as a 
    #percentage of body length.
L2 = abutt + L_petiole; #Length from the thorax-abdomen 
    #joint to the center of the abdomen mass in cm

K = LengthScaleFactor*29.3;  #K is the torsional spring constant of 
    #the thorax-petiole joint in (cm^2)*g/(rad*(s^2))
c = LengthScaleFactor*14075.8; #c is the torsional damping constant of 
    #the thorax-petiole joint in (cm^2)*g/s
rho = 1; #The density of the insect in g/(cm^3)
rhoA = 1.18*10**(-3); #The density of the air in g/(cm^3)
muA = 1.86*10**(-4); #The dynamic viscosity of air at 27C in in g/(cm*s)
g = 980.0; #g is the acceleration due to gravity in cm/(s^2)

# %% Filename suffix loop
point = 'p';
LSFtext = '_LSF_';
LEtext = '_LE_';
dotMATSuffix = '.mat';

if LengthScaleFactor >= 1:
    if LengthExtend < 1 and LengthExtend > 0:
        LSF_val = str(int(LengthScaleFactor));
        LE_val = str(int(10*LengthExtend));
        suffix = treatment + LSFtext + LSF_val + LEtext + point + LE_val \
        + dotMATSuffix;
    else:
        LSF_val = str(int(LengthScaleFactor));
        LE_val = str(int(LengthExtend));
        suffix = treatment + LSFtext + LSF_val + LEtext + LE_val \
        + dotMATSuffix;
    #End of first sub-IF statement
else: 
    if LengthExtend < 1 and LengthExtend > 0:
        LSF_val = str(int(10*LengthScaleFactor));
        LE_val = str(int(10*LengthExtend));
        suffix = treatment + LSFtext + point + LSF_val + LEtext + point \
        + LE_val + dotMATSuffix;
    else: 
        LSF_val = str(int(10*LengthScaleFactor));
        LE_val = str(int(LengthExtend));
        suffix = treatment + LSFtext + point + LSF_val + LEtext + LE_val \
        + dotMATSuffix;
    #End of second sub-IF statement
#End of filename suffix IF statement

print(suffix)

# %% More variables NOT to alter
halfwingStrokes = int(501); #Originally 100, but we need an extra half wing
    #stroke for the formal MPC.
hwbf = int(50); #wing beat frequency of the insect in Hz
timestep = int(100); #The number of timesteps we will use when interpolating
                #DO NOT CHANGE TIMESTEP SIZE
kk = int(0); #Overall counter of runs. DO NOT RESET!
i_overall = int(0); #Overall counter of runs. DO NOT RESET!
kkskip = int(1); #Overall counter OF SKIPS. Do not reset.
nn = int(1); #Counter of full runs. Do not reset!
MaxWorkers = multiprocessing.cpu_count(); #Number of workers for 
        #parallel computing. Do not reset!
RecedeFrac = 0.25; #Must be a value between 0 and 1.
                #This governs how far back the goal is shifted from the
                #original goal.
goal_index = np.arange(timestep-1,(timestep*halfwingStrokes),(RecedeFrac*100));
    #Indices for the goal (without having to calculate it every loop)
    #Note: -1 is included to account for Python's annoying indexing.

#Defining the time duration of the simulations within the parallelized loop
ti = 0.0;  # initial time in seconds
tf = 0.02;  # final time in seconds
#t_spray = np.linspace(ti, tf, timestep, endpoint = True);
t_spray = np.linspace(ti, tf, 5, endpoint = True);

print('Goal indices: ', goal_index)
print('Number of max workers is: ', MaxWorkers)

# %% Time vector
Tstore = np.linspace(0,((1/hwbf)*halfwingStrokes),(timestep*halfwingStrokes)).T;
# save('12h-AMSumOfPrimes_MPC/Tstore_MPC_hws_sp.mat','Tstore')
#savemat('Tstore_MPC_hws_sp.mat', {'Tstore': Tstore})
#print(Tstore[100])

# %% Relevant to cost function
#Goal criteria
x_g = 0; #in cm
theta_g = np.pi/4; #in radians

xdot_g = 0; #in cm/s
thetadot_g = 0; #in radians/s

#Create the sum of primes signal
signal_amp = 5; #in cm
prime_f = np.array([0.2, 0.3, 0.5, 0.7, 1.1, 1.7, 2.9, 4.3, 7.9, \
                    13.7, 19.9]); #in Hz
prime_a = (signal_amp/(2*np.pi*prime_f))*(2*np.pi*prime_f[0]); #in cm

#y-motion goal criteria (for the cost function)
y_g = prime_a[0]*np.sin(2*np.pi*prime_f[0]*Tstore) \
    +prime_a[1]*np.sin(2*np.pi*prime_f[1]*Tstore) \
    +prime_a[2]*np.sin(2*np.pi*prime_f[2]*Tstore) \
    +prime_a[3]*np.sin(2*np.pi*prime_f[3]*Tstore) \
    +prime_a[4]*np.sin(2*np.pi*prime_f[4]*Tstore) \
    +prime_a[5]*np.sin(2*np.pi*prime_f[5]*Tstore) \
    +prime_a[6]*np.sin(2*np.pi*prime_f[6]*Tstore) \
    +prime_a[7]*np.sin(2*np.pi*prime_f[7]*Tstore) \
    +prime_a[8]*np.sin(2*np.pi*prime_f[8]*Tstore) \
    +prime_a[9]*np.sin(2*np.pi*prime_f[9]*Tstore) \
    +prime_a[10]*np.sin(2*np.pi*prime_f[10]*Tstore); #in cm
    
#ydot-motion goal criteria (for the cost function)    
ydot_g = 2*np.pi*prime_a[0]*prime_f[0]*np.cos(2*np.pi*prime_f[0]*Tstore) \
        +2*np.pi*prime_a[1]*prime_f[1]*np.cos(2*np.pi*prime_f[1]*Tstore) \
        +2*np.pi*prime_a[2]*prime_f[2]*np.cos(2*np.pi*prime_f[2]*Tstore) \
        +2*np.pi*prime_a[3]*prime_f[3]*np.cos(2*np.pi*prime_f[3]*Tstore) \
        +2*np.pi*prime_a[4]*prime_f[4]*np.cos(2*np.pi*prime_f[4]*Tstore) \
        +2*np.pi*prime_a[5]*prime_f[5]*np.cos(2*np.pi*prime_f[5]*Tstore) \
        +2*np.pi*prime_a[6]*prime_f[6]*np.cos(2*np.pi*prime_f[6]*Tstore) \
        +2*np.pi*prime_a[7]*prime_f[7]*np.cos(2*np.pi*prime_f[7]*Tstore) \
        +2*np.pi*prime_a[8]*prime_f[8]*np.cos(2*np.pi*prime_f[8]*Tstore) \
        +2*np.pi*prime_a[9]*prime_f[9]*np.cos(2*np.pi*prime_f[9]*Tstore) \
        +2*np.pi*prime_a[10]*prime_f[10]*np.cos(2*np.pi*prime_f[10]*Tstore); 
        #in cm/s

#Weighting coefficients (AS OF 2019/05/10)
#c1 = x,    c2 = y,      c3 = theta,  c4 = xdot,   c5 = ydot,   c6 = thetadot
c1 = 10**9; c2 = 10**10; c3 = 10**10; c4 = 10**-5; c5 = 10**-5; c6 = 10**8; 
    #Reminder: Abdominal motion is NOT penalized. The question is centered 
    #around if the abdomen contributes to movement control, and if so, to what 
    #degree?
    
    #NOTE: IN MATLAB, the order of the coefficients was:
    #c1 = xdot, c2 = ydot, c3 = thetadot, c4 = x, c5 = y, c6 = theta

#Pack costCoefficients
costCoeff = np.array([c1, c2, c3, c4, c5, c6]);

# %% Initial conditions
            #q0 = [x, y, theta, phi, xdot, ydot, thetadot, phidot]
q0_og = np.array([0.0, 0.0, theta_g, (theta_g + np.pi), 10**-4, 10**-4, 0.0, 0.0]);
q0 = q0_og; #The initial conditions will be reset with each half wing stroke, 
            #but for now, we'll set this to the og.

betaR = q0_og[3] - q0_og[2] - np.pi; #This is the resting configuration of our 
    #torsional spring(s) = Initial abdomen angle - initial head angle - pi

# %% Pack the parameters away to send to myODE_5
#    These parameters DO NOT change 
#par = L1, L2, L3, L_petiole, rho, rhoA, muA, 
#          ahead, abutt, bhead, bbutt, K, c, g, betaR
#par = np.array([L1, L2, L3, L_petiole, rho, rhoA, muA, \
#                ahead, abutt, bhead, bbutt, K, c, g, betaR]);
#print(par)
#
#Packed and sent
#multibodyDynamics_12h.packedParameters(par, costCoeff, t, timestep, RecedeFrac);
    
# %% Calculated inertial properies of the simulated insect
#
#globalDict['m1'] = globalDict['rho']*(4/3)*np.pi*(globalDict['bhead']**2)*globalDict['ahead'];

m1 = rho*(4/3)*np.pi*(bhead**2)*ahead; #m1 is the mass of the head-thorax
m2 = rho*(4/3)*np.pi*(bbutt**2)*abutt; #m2 is the mass of the abdomen 
                #(petiole + gaster)
echead = ahead/bhead; #Eccentricity of head-thorax (unitless)
ecbutt = abutt/bbutt; #Eccentricity of gaster (unitless)
I1 = (1/5)*m1*(bhead**2)*(1 + echead**2); #Moment of inertia of the 
                #head-thorax
    #The issue corrected on 1/31/19
    #Recall the parallel axis theorem: I = I_centerOfMass + m*(d^2)
    #Where m is the mass of the object, and d is the perpendicular distance
        #between the axis of rotation and the object.
I2 = (1/5)*m2*(bbutt**2)*(1 + ecbutt**2) + (m2*L_petiole**2); #Moment of 
                #inertia of the abdomen (in grams*(cm^2))
                
S_head = np.pi*(bhead**2); #This is the surface area of the object 
                #experiencing drag. In this case, it is modeled as a sphere.
S_butt = np.pi*(bbutt**2); #This is the surface area of the object 
                #experiencing drag. In this case, it is modeled as a sphere.
                
# %% Define global variables
globalDict = OrderedDict({"L1": L1, "L2": L2, "L3": L3, "L_petiole": L_petiole, 
              "ahead": ahead, "abutt": abutt, "bhead": bhead, "bbutt": bbutt,
              "K": K, "c": c, "rho": rho, "rhoA": rhoA, "muA": muA, "g": g,
              "m1": m1, "m2": m2, "echead": echead, "ecbutt": ecbutt, "I1": I1,
              "I2": I2, "S_head": S_head, "S_butt": S_butt, "betaR": betaR});

# Convert the dictionary to a list. Apparently @jit needs arrays or lists
globalList = [v_uni for v_uni in globalDict.values()]

# %% Prescribe the storage data
#xx_og = np.zeros((timestep,len(q0_og))); #This will be the vector containing 
#                                        #the state variables in the 
#                                        #parellelized loop.
#xx = xx_og; #The vector containing the state variables will be reset with each 
#            #half wing stroke, but for now, we'll set this to the og.
# tt = np.linspace(0,(1/hwbf),timestep); #This will be the time vector in the 
                                #parallelized loop for interpolation reasons.
#PartPath = ([None]*int(numOfTrajectories)); #This creates the number of 
                                       #partial paths necessary for the 
                                       #receding horizon
numOfPartialPaths = int((halfwingStrokes-1)*(1/RecedeFrac)); #An integer value 
                                            #of the number of partial paths
pre_Winstore = ([None]*numOfPartialPaths);
# pre_Winstore = ([None]*int(50))
#print(len(PartPath))  

# %% Generating the simulations

#Start the "full run" loop (a.k.a. a virtual moth)
for nn in np.arange(1,FullRuns+1):
    #Note: I need to index nn starting from 1 because of filename reasons
    
    #Start the iteration of consecutive partial paths
    for i in np.arange(0,numOfPartialPaths):
#     for i in range(0,int(50)):
        #Overall counter
        i_overall = i_overall+1;
        
        #This is where I would normally re-seed my random number generator.
        #Insert re-seed here: 
        #[RE-SEED]
        
        #Assign randomized applied efforts (F, alpha, tau_abdomen, tau_wing)
        #F: the magnitude of the applied force
            #For LSF >= 1
        F_array = 44300*np.random.rand(numOfTrajectories)*(LengthScaleFactor**3);
            #F is a proxy for the magnitude of the aerodynamic vector in g*cm/(s^2)
            
        #alpha: the direction of the applied force
        alpha_array = 2*np.pi*np.random.rand(numOfTrajectories);
            #alpha is the angle of the aerodynamic vector with respect to 
            #the head-thorax mid-line in radians
        
        #tau0: The magnitude (and direction) of the applied abdominal torque
        tau0_array = (100000*10*(2*(np.random.rand(numOfTrajectories)-0.5))*(LengthScaleFactor**4))
            #The applied abdominal torque in g*(cm^2)/(s^2)
            
        #tau_w: The magnitude (and direction) of the applied wing torque
        tau_w_array = (100000*(2*(np.random.rand(numOfTrajectories)-0.5))*(LengthScaleFactor**4))
#         tau_w = np.zeros(numOfTrajectories); #If model 12h, use tau_w = 0
            #The applied abdominal torque in g*(cm^2)/(s^2)
        
        #Define the goal criteria for y and ydot BEFORE the parallelized loop
        y_g_thisPartPath = y_g[int(goal_index[i])]; #in cm
        ydot_g_thisPartPath = ydot_g[int(goal_index[i])]; #in cm/s
        
        #Pack goal criteria for this particular half wing stroke
        goalCriteria = np.array([x_g, y_g_thisPartPath, theta_g, xdot_g, 
                                 ydot_g_thisPartPath, thetadot_g]);
        
#        bigQ = [None]*int(numOfTrajectories); #This will be a 100 x 8 matrix
#        cost = [None]*int(numOfTrajectories); #This will be a single value
#        NewICs = [None]*int(numOfTrajectories); #This will be an 8 x 1 vector
#        check = [None]*int(numOfTrajectories); #This will be a 4 x 1 vector
        PartPath = [None]*int(numOfTrajectories); #This will be a 4 x 1 list
        
#        importlib.reload(multibodyDynamics_12h)
        
        #Using multi-processing to generate simulations in a parallelized form
        importlib.reload(multibodyDynamics_12h)
        p = multiprocessing.Pool(MaxWorkers);
        print("About to start the loop")
#        stt = time.time()   
        bb = p.map(functools.partial(multibodyDynamics_12h.generateSimulations, 
                                     t_spray = t_spray, 
                                     q0 = q0, 
                                     F_array = F_array, 
                                     alpha_array = alpha_array, 
                                     tau0_array = tau0_array, 
                                     tau_w_array = tau_w_array, 
                                     timestep = timestep,
                                     RecedeFrac = RecedeFrac,
                                     costCoeff = costCoeff,
                                     goalCriteria = goalCriteria,
                                     globalList = globalList),
                                     range(numOfTrajectories));
        print("The parallelized loop has finished")
            #Note bb is going to be a 2500 x 1 nested list
#       print(time.time() -stt)
        
        #To close the multi-threading, and join the threads
        p.close()
        p.join()
#        print(time.time() -stt)
        
        just 
#        np.array(bb).shape 
        
        #Multi-processing ends here.
        
        #Extracting the lowest cost function value location
        extractedCost = [None]*int(numOfTrajectories+1); 
        
        for j in np.arange(0,numOfTrajectories):
            extractedCost[j] = bb[0][j][1];
        
        #Overall counter (might use this instead of i_overall)
        kk = kk+numOfTrajectories; #DO NOT RESET
        
        #Find the indices of the lowest cost function value
        lowestCostIndex = np.where(np.array(extractedCost) == min(extractedCost)); 
        lowestCostInt = int(lowestCostIndex[0]); #Integer value of the index

        winningList = [None]*int(9);
        
        winningList[0] = np.array([q0]); #The initial conditions for this spray
        winningList[1] = float(F_array[lowestCostInt]); #F for this spray
        winningList[2] = float(alpha_array[lowestCostInt]); #alpha for this spray
        winningList[3] = float(tau0_array[lowestCostInt]); #abdominal torque for this spray
        winningList[4] = float(tau_w_array[lowestCostInt]); #wing torque for this spray
        winningList[5] = np.array(bb[0][lowestCostInt][0]); #StateVars for this spray
        winningList[6] = float(bb[0][lowestCostInt][1]); #cost function value for this spray
        winningList[7] = np.array(bb[0][lowestCostInt][2]); #NEW initial conditions for this spray
        winningList[8] = np.array(bb[0][lowestCostInt][3]); #A 4 x 1 array of:
                                #[F, alpha, tau0, and tau_w] for this spray

#         PartPath = winningList;
        pre_Winstore[i] = winningList;
    
        #Set the new initial conditions for the next spray
        q0 = winningList[7];
        
        #Print out the progress of the simulations
        print('On Full Run #',nn,', partial path: ', i, ' of ', \
              numOfPartialPaths, end="\r")
        #End of Partial paths loop (i)
    
    #Create the filename for the saved data
    prefix = 'pre_Winstore_{}_'.format(nn+shift); 
        #Reminder: nn is number of FullRuns, shift is shifting this value
    filename = prefix + suffix;
    print(filename)
    
    #Save the pre_Winstore file
    savemat(filename, {'pre_Winstore': pre_Winstore})
    
    #Now we reset our initial conditions (q0) and temporary storage (xx)
    #for the next full run.
    
    #Our initial conditions in the following order:
    #q0 = [x, y, theta, phi, xdot, ydot, thetadot, phidot]
    q0 = q0_og;
    
    #A 100x8 matrix of zeros
#    xx = xx_og;
    
