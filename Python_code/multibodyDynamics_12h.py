from scipy.integrate import odeint
import numpy as np
#import pandas as pd
#import os
#from scipy.integrate import odeint #This was the original ODE solver we were using
#import math
from numba import jit

## The MATLAB version is "myODE_5.m"
@jit(cache = True)
def myODE_5(q0, t_spray, F, alpha, tau0, tau_w, L1, L2, L3, L_petiole, ahead, 
            abutt, bhead, bbutt, K, c, rho, rhoA, muA, g, m1, m2, echead, 
            ecbutt, I1, I2, S_head, S_butt, betaR):
            #def myODE_5(Q,t, par, F, alpha, tau0, tau_w):
            #Unpack the state vector (THE ORDER MATTERS)
    x, y, theta, phi, xd, yd, thetad, phid = q0 
#    print(type(x),type(y),type(theta),type(phi),type(xd),type(yd),type(thetad),type(phid))
                
#            m1 = rho*(4/3)*np.pi*(bhead**2)*ahead; #m1 is the mass of the head-thorax
#            m2 = rho*(4/3)*np.pi*(bbutt**2)*abutt; #m2 is the mass of the abdomen 
#                #(petiole + gaster)
#            echead = ahead/bhead; #Eccentricity of head-thorax (unitless)
#            ecbutt = abutt/bbutt; #Eccentricity of gaster (unitless)
#            I1 = (1/5)*m1*(bhead**2)*(1 + echead**2); #Moment of inertia of the 
#                #head-thorax
#                #The issue corrected on 1/31/19
#                #Recall the parallel axis theorem: I = I_centerOfMass + m*(d^2)
#                #Where m is the mass of the object, and d is the perpendicular distance
#                #between the axis of rotation and the object.
#            I2 = (1/5)*m2*(bbutt**2)*(1 + ecbutt**2) + (m2*L_petiole**2); #Moment of 
#                #inertia of the abdomen (in grams*(cm^2))
#                
#            S_head = np.pi*bhead**2; #This is the surface area of the object 
#                #experiencing drag. In this case, it is modeled as a sphere.
#            S_butt = np.pi*bbutt**2; #This is the surface area of the object 
#                #experiencing drag. In this case, it is modeled as a sphere.
                
    #Reynolds number calculation:
    Re_head = rhoA*(np.sqrt((xd**2)+(yd**2)))*(2*bhead)/muA; #dimensionless number
    Re_butt = rhoA*(np.sqrt((xd**2)+(yd**2)))*(2*bbutt)/muA; #dimensionless number
                
    #Coefficient of drag stuff:
    Cd_head = 24/np.abs(Re_head) + 6/(1 + np.sqrt(np.abs(Re_head))) + 0.4;
    Cd_butt = 24/np.abs(Re_butt) + 6/(1 + np.sqrt(np.abs(Re_butt))) + 0.4;
    
        #These are the coefficients for our acceleration equations imported from Mathematica 
            #(and MATLAB). Careful, this'll get messy.
    h1 = m1 + m2;
    h2 = (-1)*L1*m1*np.sin(theta);
    h3 = (-1)*L2*m2*np.sin(phi);
    h4 = L1*m1*np.cos(theta);
    h5 = L2*m2*np.cos(phi);
    h6 = ((-1)*F*np.cos(alpha+theta)+(1/2)*Cd_butt*rhoA*S_butt*np.abs(xd)*xd
          +(1/2)*Cd_head*rhoA*S_head*np.abs(xd)*xd+(-1)*L1*m1*np.cos(theta)*thetad**2
          +(-1)*L2*m2*np.cos(phi)*phid**2)
    h7 = (g*(m1+m2)+(1/2)*Cd_butt*rhoA*S_butt*np.abs(yd)*yd+(1/2)*Cd_head*rhoA
          *S_head*np.abs(yd)*yd+(-1)*L1*m1*thetad**2*np.sin(theta)
          +(-1)*F*np.sin(alpha+theta)+(-1)*L2*m2*phid**2*np.sin(phi));
                                     #This is where non-linearity would go ')**3' ---v
    h8 = ((-1)*tau0+g*L1*m1*np.cos(theta)+(-1)*K*((-1)*betaR+(-1)*np.pi+
           (-1)*theta+phi)+(-1)*c*((-1)*thetad+phid)+(-1)*F*L3*np.sin(alpha)-tau_w)
    h9 = (tau0+g*L2*m2*np.cos(phi)+K*((-1)*betaR+(-1)*np.pi+(-1)*theta+phi)+c*((-1)*thetad+phid));
                        #^-- This is where non-linearity would go ')**3'
    h10 = I1+(L1**2)*m1;
    h11 = I2+(L2**2)*m2;

    #x double dot
    xdd = ((-1)*(h10*h11*h1**2+(-1)*h11*h1*h2**2
            +(-1)*h10*h1*h3**2+(-1)*h11*h1*h4**2+h3**2*h4**2
            +(-2)*h2*h3*h4*h5+(-1)*h10*h1*h5**2+h2**2*h5**2)**(-1)*(h10*h11*h1*h6
             +(-1)*h11*h4**2*h6+(-1)*h10*h5**2*h6+h11*h2*h4*h7+h10*h3*h5*h7
             +(-1)*h11*h1*h2*h8+(-1)*h3*h4*h5*h8+h2*h5**2*h8
             +(-1)*h10*h1*h3*h9+h3*h4**2*h9+(-1)*h2*h4*h5*h9))
  
    #y double dot
    ydd = ((-1)*((-1)*h10*h11*h1**2+h11*h1*h2**2+h10*h1*h3**2
            +h11*h1*h4**2+(-1)*h3**2*h4**2+2*h2*h3*h4*h5
            +h10*h1*h5**2+(-1)*h2**2*h5**2)**(-1)*((-1)*h11*h2*h4*h6
                          +(-1)*h10*h3*h5*h6+(-1)*h10*h11*h1*h7+h11*h2**2*h7
                          +h10*h3**2*h7+h11*h1*h4*h8+(-1)*h3**2*h4*h8
                          +h2*h3*h5*h8+h2*h3*h4*h9+h10*h1*h5*h9+(-1)*h2**2*h5*h9))

    #theta double dot
    thetadd = ((-1)*((-1)*h10*h11*h1**2+h11*h1*h2**2+h10*h1*h3**2
                +h11*h1*h4**2+(-1)*h3**2*h4**2+2*h2*h3*h4*h5
                +h10*h1*h5**2+(-1)*h2**2*h5**2)**(-1)*(h11*h1*h2*h6
                              +h3*h4*h5*h6+(-1)*h2*h5**2*h6+h11*h1*h4*h7
                              +(-1)*h3**2*h4*h7+h2*h3*h5*h7+(-1)*h11*h1**2*h8
                              +h1*h3**2*h8+h1*h5**2*h8+(-1)*h1*h2*h3*h9
                              +(-1)*h1*h4*h5*h9))

    #phi double dot
    phidd = ((-1)*((-1)*h10*h11*h1**2+h11*h1*h2**2+h10*h1*h3**2
              +h11*h1*h4**2+(-1)*h3**2*h4**2+2*h2*h3*h4*h5
              +h10*h1*h5**2+(-1)*h2**2*h5**2)**(-1)*(h10*h1*h3*h6
                            +(-1)*h3*h4**2*h6+h2*h4*h5*h6+h2*h3*h4*h7
                            +h10*h1*h5*h7+(-1)*h2**2*h5*h7+(-1)*h1*h2*h3*h8
                            +(-1)*h1*h4*h5*h8+(-1)*h10*h1**2*h9+h1*h2**2*h9
                            +h1*h4**2*h9))
    
#    print(type(xd),type(yd),type(thetad),type(phid),xdd.shape,ydd.shape,thetadd.shape,phidd.shape)
    #xdd[0], ydd[0], thetadd[0], phidd[0]
    return(np.array([xd, yd, thetad, phid, xdd, ydd, thetadd, phidd]))

    #Generate simulations (in parallelized cores)
def generateSimulations(simNum, t_spray, q0, F_array, alpha_array, tau0_array, 
                        tau_w_array, timestep, RecedeFrac, costCoeff, 
                        goalCriteria, globalList):
    F = F_array[simNum];
    alpha = alpha_array[simNum];
    tau0 = tau0_array[simNum];
    tau_w = tau_w_array[simNum];
    print("F, alpha, tau0, and tau_w are: ", F, alpha, tau0, tau_w)
    print("Data types of the above are: ", type(F), type(alpha), type(tau0), type(tau_w))
    
    NewIC_index = int(timestep*RecedeFrac);
    
#    print("test 1a")
#    q0 = list(q0)
#    t_spray = list(t_spray)
    print("Vars loaded, about to start ODEINT")
            
    Q = odeint(myODE_5, q0, t_spray, args = (F, alpha, tau0, tau_w, *globalList))
    
    xx = np.array(Q);
    print("Finished ODEINT")

    print("Type Q is: ", type(Q))
    print("Type xx is: ", type(xx))
    print("Shape of xx is: ", xx.shape)
    print("The type of costCoeff[3] is: ", type(costCoeff[3]))
    
    #Cost function value
    cost = (costCoeff[3]*((xx[-1,4]-goalCriteria[3])**2)
    +costCoeff[4]*((xx[-1,5]-goalCriteria[4])**2)
    +costCoeff[5]*((xx[-1,6]-goalCriteria[5])**2)
    +costCoeff[0]*((xx[-1,0]-goalCriteria[0])**2)
    +costCoeff[1]*((xx[-1,1]-goalCriteria[1])**2)
    +costCoeff[2]*((xx[-1,2]-goalCriteria[2])**2))
    
    print("Cost is: ",cost)
    print("Type of cost: ", type(cost))
    
    print("25th value of x array is: ", float(Q[NewIC_index,0]))
#    print(xx[int(timestep*RecedeFrac),1])
#    print(xx[int(timestep*RecedeFrac),2])
#    print(xx[int(timestep*RecedeFrac),3])
#    print(xx[int(timestep*RecedeFrac),4])
#    print(xx[int(timestep*RecedeFrac),5])
#    print(xx[int(timestep*RecedeFrac),6])
#    print(xx[int(timestep*RecedeFrac),7])
    
    #Calculate the new initial conditions
    NewICs = np.array([xx[NewIC_index,0], xx[NewIC_index,1], xx[NewIC_index,2], 
                       xx[NewIC_index,3], xx[NewIC_index,4], xx[NewIC_index,5], 
                       xx[NewIC_index,6], xx[NewIC_index,7]])
    
    print("New ICs are: ", NewICs)
    print("The type of new ICs is: ", type(NewICs))
    
#    print("test 5")
            #This will check if the applied efforts are saved correctly
    check = np.array([F, alpha, tau0, tau_w]);
    
    print("Check is: ", check)
    print("The type of check is: ", type(check))
    
#    print("test 6")
#    PartPath[simNum] = list(np.array([bigQ]), float(cost), np.array([NewICs]), 
#            np.array([check]));
    PartPath = [Q, cost, NewICs, check];
    
#    print("PartPath is: ", PartPath)
    print("The type of PartPath is: ", type(PartPath))
    
#    print("test 7")    
    return(PartPath)
    #End of numOfTrajectories loop (j) (for solving ODEs)
