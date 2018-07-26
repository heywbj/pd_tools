import itertools
import logging
import matplotlib.pyplot as pyplot
import math
import numpy as np
import os
import pprint

import pd_tools

FIMMWAVE = r'C:\Program Files (x86)\PhotonD\Fimmwave\bin64\fimmwave.exe'
wd = r'D:\Warren\2017-10-17-group-velocities'
material_db = 'ull-material-db.mat'

# To debug, use 'winpty python.exe match_vg.py'

if __name__ == "__main__":
    connection = pd_tools.PDApp(path=FIMMWAVE, batch=True)
    with connection as app:
        app.setwdir(wd)
        app.addsubnode('fimmwave_prj', 'group velocity study')
        prj = app.subnodes[1]
        prjidx = 0

        prjidx += 1
        variables = pd_tools.fimm.add_vars(prj, prjidx, 'variables', {
            # base parameters
            'w_sim': '32',
            't_sim': '8',
            't_clad_u': '1',
            't_clad_d': '1',
            'w_core': '2.8',
            't_core': '0.058',
            'y_offset': '0',

            # derived parameters
            'w_rest': '(w_sim - w_core)/2',
            't_clad': 't_clad_u + t_clad_d',
            't_clad_u_core': 't_clad_u - t_core/2',
            't_clad_d_core': 't_clad_d - t_core/2',
            't_air_u': 't_sim/2 - t_clad_u - y_offset',
            't_air_d': 't_sim/2 - t_clad_d + y_offset',
        })

        cladding = 'SiO2-sputter-post-anneal'
        prjidx += 1
        wg = pd_tools.fimm.add_rwg(prj, prjidx, cladding,
            [
                {
                    'width': 'w_rest',
                    'layers': [
                        {'size': 't_air_d', 'material': 'AIR'},
                        {'size': 't_clad', 'material': cladding},
                        {'size': 't_air_u', 'material': 'AIR'},
                    ]
                },
                {
                    'width': 'w_core',
                    'layers':[
                        {'size': 't_air_d', 'material': 'AIR'},
                        {'size': 't_clad_d_core', 'material': cladding},
                        {'size': 't_core', 'material':'Si3N4-LPCVD-rogue-valley', 'cfseg': 1},
                        {'size': 't_clad_u_core', 'material': cladding},
                        {'size': 't_air_u', 'material': 'AIR'},
                    ]
                },
                {
                    'width': 'w_rest',
                    'layers':[
                        {'size': 't_air_d', 'material': 'AIR'},
                        {'size': 't_clad', 'material': cladding},
                        {'size': 't_air_u', 'material': 'AIR'},
                    ]
                },
            ],
            os.path.join(wd, material_db),
        )
        wg.lhsbc.pmlpar = 5;
        wg.rhsbc.pmlpar = 5;

        pd_tools.fimm.config_solver(wg,
            {
                'autorun': 1, # allow fimmprop to auto-build 0=no 1=yes
                'speed': 0, # optimisation: 0=best 1=fast
                'mintefrac': 0,
                'maxtefrac': 100,
                'maxnmodes': 2,
                # 'evstart': 1e50, # search range for modes as neff/beta
                # 'evend': -1e50,
                'nx': 1024,
                'ny': 384,
            },
            {
                'lambda': 1.55,
                'hcurv': 0,
                'solvid': 73, # FMM
                'hsymmetry': 0, # 0=none 1=Ex 2=Ey 3=both
                'vsymmetry': 0, # 0=none 1=Ex 2=Ey 3=both
                'buff': 'V2 30 0 1 300 300 15 25 0 5 5',
            },
        )

        connection.toggle_mode()

        # keep track of group indices to plot in scatter fashion
        tpairs = (
            (0.5,   0.5),
            (0.40,  0.5),
            (0.45,  0.5),
            (0.55,  0.5),
            (0.60,  0.5),
        )
        # tpairs = ((0.5,0.5),)

        tepairs = (
            (50,100),
            (0,50),
        )

        r1 = np.arange(1, 2, 0.1);
        r2 = np.arange(2, 5, 0.25);

        # r1 = np.arange(1,2,1);
        # r2 = np.arange(2,3,1);

        for t_up, t_down in tpairs:
            x = []
            y = []

            for w_core in np.concatenate((r1, r2)):
                print('t:%s/%s w:%s' % (t_up, t_down, w_core))

                for minte,maxte in tepairs:
                    variables.setvariable('w_core', w_core)
                    variables.setvariable('t_clad_u', t_up)
                    variables.setvariable('t_clad_d', t_down)

                    wg.evlist.mlp.mintefrac = minte
                    wg.evlist.mlp.maxtefrac = maxte

                    # first solve for coarse
                    # wg.evlist.mlp.nx = 128;
                    # wg.evlist.mlp.ny = 48;
                    # wg.evlist.update()

                    # then refine
                    wg.evlist.mlp.nx = 512;
                    wg.evlist.mlp.ny = 192;
                    # wg.evlist.polishevs()
                    wg.evlist.update()

                    # Iterate through mode list
                    print('found %s modes' % len(wg.evlist.list))
                    for mode in wg.evlist.list:
                        neff = mode.neff()
                        tefrac = mode.modedata.tefrac

                        # discard modes that don't match
                        if tefrac > maxte or tefrac < minte:
                            continue

                        # discard modes with too much loss
                        if abs(neff.imag) > 1e-5:
                            print(neff,tefrac)
                        else:
                            mode.modedata.update(1)
                            neffg = mode.modedata.neffg

                            print(neff,tefrac, neffg)
                            if neffg > 2:
                                continue
                            x.append(w_core);
                            y.append(neffg);

            pyplot.figure(1)
            pyplot.scatter(x,y)
            pyplot.xlabel('wg width (um)')
            pyplot.ylabel('group index')
            pyplot.ylim((1.55,1.60))
            pyplot.savefig(os.path.join(wd,
                    'scatter-neffg_58nm_up-%0.2f_down-%0.2f.png' % (t_up, t_down)))
            pyplot.clf()

        connection.toggle_mode()
        prj.savetofile(os.path.join(wd, 'match_vg.prj'))

        app.exit()
