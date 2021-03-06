## Copyright (C) 2011 Stellenbosch University
##
## This file is part of SUCEM.
##
## SUCEM is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## SUCEM is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with SUCEM. If not, see <http://www.gnu.org/licenses/>. 
##
## Contact: cemagga@gmail.com 
# Authors:
# Neilen Marais <nmarais@gmail.com>

from __future__ import division

import pickle
import numpy as np
import sys
import dolfin
sys.path.append('../../')
from sucemfem.Consts import eps0, mu0, c0, Z0
from sucemfem.Utilities.Converters import as_dolfin_vector
import sucemfem.Utilities.Optimization

from sucemfem import Geometry 
from sucemfem.Sources.PostProcess import ComplexVoltageAlongLine
from sucemfem.PostProcessing import CalcEMFunctional
from sucemfem.PostProcessing.power_flux import SurfaceFlux, VariationalSurfaceFlux

# Enable dolfin's form optimizations
sucemfem.Utilities.Optimization.set_dolfin_optimisation()


# fname = 'data/f-1000000000.000000_o-2_s-0.299792_l-0.100000_h-0.166667'
# fname = 'data/f-1000000000.000000_o-2_s-0.299792_l-0.100000_h-0.083333'

order = 2
fnames = {2:['data/f-1000000000.000000_o-2_s-0.074948_l-0.100000_h-0.016667', # h60 
             'data/f-1000000000.000000_o-2_s-0.074948_l-0.100000_h-0.020833', # h48 
             'data/f-1000000000.000000_o-2_s-0.074948_l-0.100000_h-0.027778', # h36 
             'data/f-1000000000.000000_o-2_s-0.074948_l-0.100000_h-0.041667', # h24 
             'data/f-1000000000.000000_o-2_s-0.074948_l-0.100000_h-0.083333', # h12 
             'data/f-1000000000.000000_o-2_s-0.074948_l-0.100000_h-0.166667',  # h6  
             ],
          1:['data/f-1000000000.000000_o-1_s-0.074948_l-0.100000_h-0.013889', # h72
             'data/f-1000000000.000000_o-1_s-0.074948_l-0.100000_h-0.016667', # h60
             'data/f-1000000000.000000_o-1_s-0.074948_l-0.100000_h-0.020833', # h48
             'data/f-1000000000.000000_o-1_s-0.074948_l-0.100000_h-0.027778', # h36
             'data/f-1000000000.000000_o-1_s-0.074948_l-0.100000_h-0.041667', # h24
             'data/f-1000000000.000000_o-1_s-0.074948_l-0.100000_h-0.083333', # h12
             'data/f-1000000000.000000_o-1_s-0.074948_l-0.100000_h-0.166667', # h6  
             ]
          }

hs = [] ; volts = [] ; sfluxes = [] ; vfluxes = []

def calcs(fname):
    data = pickle.load(open(fname+'.pickle'))
    mesh = dolfin.Mesh(data['meshfile'])
    elen = np.array([e.length() for e in dolfin.edges(mesh)])
    ave_elen = np.average(elen)
    material_meshfn = dolfin.MeshFunction('uint', mesh, data['materialsfile'])
    V = dolfin.FunctionSpace(mesh, "Nedelec 1st kind H(curl)", data['order'])
    x = data['x']
    x_r = as_dolfin_vector(x.real)
    x_i = as_dolfin_vector(x.imag)
    E_r = dolfin.Function(V, x_r)
    E_i = dolfin.Function(V, x_i)
    k0 = 2*np.pi*data['freq']/c0

    n = V.cell().n

    ReS = (1/k0/Z0)*dolfin.dot(n, (dolfin.cross(E_r, -dolfin.curl(E_i)) +
                                   dolfin.cross(E_i, dolfin.curl(E_r))))*dolfin.ds
    energy_flux = dolfin.assemble(ReS)
    surface_flux = SurfaceFlux(V)
    surface_flux.set_dofs(x)
    surface_flux.set_k0(k0)
    energy_flux2 = surface_flux.calc_flux()
    assert(np.allclose(energy_flux, energy_flux2, rtol=1e-8, atol=1e-8))    

    def boundary(x, on_boundary):
        return on_boundary
    E_r_dirich = dolfin.DirichletBC(V, E_r, boundary)
    x_r_dirich = as_dolfin_vector(np.zeros(len(x)))
    E_r_dirich.apply(x_r_dirich)
    E_i_dirich = dolfin.DirichletBC(V, E_i, boundary)
    x_i_dirich = as_dolfin_vector(np.zeros(len(x)))
    E_i_dirich.apply(x_i_dirich)
    x_dirich = x_r_dirich.array() + 1j*x_i_dirich.array()

    emfunc = CalcEMFunctional(V)
    emfunc.set_k0(k0)
    cell_domains = dolfin.CellFunction('uint', mesh)
    cell_domains.set_all(0)
    cell_region = 1
    boundary_cells = Geometry.BoundaryEdgeCells(mesh)
    boundary_cells.mark(cell_domains, cell_region)
    emfunc.set_cell_domains(cell_domains, cell_region)

    emfunc.set_E_dofs(x)
    emfunc.set_g_dofs(1j*x_dirich.conjugate()/k0/Z0)
    var_energy_flux = emfunc.calc_functional().conjugate()
    var_surf_flux = VariationalSurfaceFlux(V)
    var_surf_flux.set_dofs(x)
    var_surf_flux.set_k0(k0)
    var_energy_flux2 = var_surf_flux.calc_flux()
    assert(np.allclose(var_energy_flux, var_energy_flux2, rtol=1e-8, atol=1e-8))

    complex_voltage = ComplexVoltageAlongLine(V)
    complex_voltage.set_dofs(x)

    volts = complex_voltage.calculate_voltage(*data['source_endpoints'])

    result = dict(h=ave_elen, order=order, volts=volts,
                  sflux=energy_flux, vflux=var_energy_flux)


    print 'source power: ', volts*data['I']
    print 'energy flux:      ', energy_flux
    print 'var energy flux: ', var_energy_flux

    # print '|'.join(str(s) for s in ('', volts*data['I'], energy_flux,
    #                                 var_energy_flux, ''))

    return result

for fname in fnames[order][::-1]:
    print fname
    res = calcs(fname)
    hs.append(res['h'])
    volts.append(res['volts'])
    sfluxes.append(res['sflux'])
    vfluxes.append(res['vflux'])

hs = np.array(hs)
volts = np.array(volts)

vflux_gradients_unity = np.gradient(np.real(vfluxes))
vflux_gradients = vflux_gradients_unity/np.gradient(hs)
vflux_log = np.log(np.abs(vflux_gradients))
sflux_gradients_unity = np.gradient(np.real(sfluxes))
sflux_gradients = sflux_gradients_unity/np.gradient(hs)
sflux_log = np.log(np.abs(sflux_gradients))
volts_gradients_unity = np.gradient(np.abs(np.real(volts)))
volts_gradients = volts_gradients_unity/np.gradient(hs)
volts_log = np.log(np.abs(volts_gradients))



vflux_log_h = np.log(hs)

# import pylab
# pylab.figure(3)
# pylab.hold(0)
# pylab.plot(-vflux_log_h, vflux_log, label='vflux')
# pylab.hold(1)
# pylab.plot(-vflux_log_h, sflux_log, label='sflux')
# pylab.plot(-vflux_log_h, volts_log, label='volts')
# pylab.grid(1)
# pylab.legend(loc=0)
# pylab.figure(4)
# pylab.hold(0)
# pylab.plot(hs, vfluxes, label='vflux')
# pylab.hold(1)
# pylab.plot(hs, sfluxes, label='sflux')
# pylab.plot(hs, -volts, label='volts')
# pylab.grid(1)
# pylab.legend(loc=0)
