import itertools
import logging
import matplotlib.pyplot as pyplot
import math
import numpy
import os
import pprint

import pd_tools

logging.basicConfig()

FIMMWAVE = r'C:\Program Files (x86)\PhotonD\Fimmwave\bin64\fimmwave.exe'
wd = r'D:\Warren\2017-10-17-testing'

n_sio = 1.443
n_sin = 1.93

w_sim = 100
t_sim = 12
nx = 500
ny = 240

if __name__ == "__main__":

    dat_file = os.path.join(wd,'scat.dat')
    if os.path.isfile(dat_file):
        os.remove(dat_file)

    connection = pd_tools.PDApp(path=FIMMWAVE, batch=True)
    with connection as app:
        app.setwdir(wd)
        app.addsubnode('fimmwave_prj', 'spot size converter')
        prj = app.subnodes[1]

        # variables node
        variables = pd_tools.fimm.add_vars(prj, 1, 'variables', {
            # base parameters
            'w_sim': w_sim,
            't_sim': t_sim,
            't_clad_u': '3',
            't_clad_d': '3',
            'w_core': '2.8',
            't_core': '0.090',
            'y_offset': '0',

            # derived parameters
            'w_rest': '(w_sim - w_core)/2',
            't_clad': 't_clad_u + t_clad_d',
            't_clad_u_core': 't_clad_u - t_core/2',
            't_clad_d_core': 't_clad_d - t_core/2',
            't_air_u': 't_sim/2 - t_clad_u - y_offset',
            't_air_d': 't_sim/2 - t_clad_d + y_offset',
        })

        #
        # fiber node
        #
        fiber = pd_tools.fimm.add_mwg(prj, 2, 'fiber', 'w_sim', 't_sim',
            [
                {
                    'type': 'ellipse',
                    'x': 'w_sim/2',
                    'y': 't_sim/2',
                    'width': 14,
                    'height': 14,
                    'nr': 1.49,
                },
                {
                    'type': 'rectangle',
                    'x': 'w_sim/2',
                    'y': 't_sim/2',
                    'width': 'w_sim',
                    'height': 't_sim',
                    'nr': 1.443,
                },
            ]
        )

        #
        # rectangular waveguide node
        #
        wg = pd_tools.fimm.add_rwg(prj, 3, 'waveguide',
            [
                {
                    'width': 'w_rest',
                    'layers':[
                        {'size': 't_air_d', 'nr': 1},
                        {'size': 't_clad', 'nr': n_sio},
                        {'size': 't_air_u', 'nr': 1},
                    ]
                },
                {
                    'width': 'w_core',
                    'layers':[
                        {'size': 't_air_d', 'nr': 1},
                        {'size': 't_clad_d_core', 'nr': n_sio},
                        {'size': 't_core', 'nr': n_sin},
                        {'size': 't_clad_u_core', 'nr': n_sio},
                        {'size': 't_air_u', 'nr': 1},
                    ]
                },
                {
                    'width': 'w_rest',
                    'layers':[
                        {'size': 't_air_d', 'nr': 1},
                        {'size': 't_clad', 'nr': n_sio},
                        {'size': 't_air_u', 'nr': 1},
                    ]
                },
            ]
        )

        #
        # configure solvers
        #
        pd_tools.fimm.config_solver(fiber,
            {
                'autorun': 1,
                'speed':  0,
                'mintefrac': 100,
                'maxtefrac': 100,
                'maxnmodes': 1,
                'evstart': 1e50,
                'evend': -1e50,
                'nx': nx,
                'ny': ny,
            },
            {
                'lambda': 1.55,
                'hcurv': 0,
                'solvid': 23, # FDM Solver (real/te semivectorial)
                'hsymmetry': 3, # both
                'vsymmetry': 3, # both
                'buff': 'V1 {nx} {ny} 0 3 0.000100 16'.format(nx=nx, ny=ny),
                # V1 nx ny (0=3d, 1=quasi2d[xz], 2=quasi2d[yz]) (always 1?)
                # RIX-tolerance, SFoversample
            },
        )

        pd_tools.fimm.config_solver(wg,
            {
                'autorun': 1,
                'speed': 0,
                'mintefrac': 50,
                'maxtefrac': 100,
                'maxnmodes': 16,
                'evstart': 1e50,
                'evend': -1e50,
                'nx': nx,
                'ny': ny,
            },
            {
                'lambda': 1.55,
                'hcurv': 0,
                'solvid': 17, # FMM
                'hsymmetry': 3, # both
                'vsymmetry': 0, # none
                'buff': 'V2 30 0 1 300 300 15 25 0 5 5',
            },
        )

        #
        # fimmprop device
        #
        coupler = pd_tools.fimm.add_device(prj, 4, 'edge coupler',
            [
                {
                    'type': 'wgsect',
                    'wg': '../fiber',
                    'length': 50,
                    'copy_molab': 1,
                },
                {
                    'type': 'sjoint',
                    'method': 0, # complete
                },
		{
                    'type': 'wgsect',
                    'wg': '../waveguide',
                    'length': 500,
                    'copy_molab': 1,
                }
            ]
        )

        #
        # sweep
        #

        def get_amf(t_core, t_u_clad, t_l_clad, y_offset, w_core):
            return 't%.3f_u%.1f_l%.1f_y%.3f_w%.1f.amf' % (
                t_core,
                t_u_clad,
                t_l_clad,
                y_offset,
                w_core,
            )

        def get_png(t_core, t_u_clad, t_l_clad, y_offset):
            return 't%.3f_u%.1f_l%.1f_y%.3f.png' % (
                t_core,
                t_u_clad,
                t_l_clad,
                y_offset,
            )

        t_cores = [0.09, 0.175]
        t_u_clads = [1, 2, 4]
        t_l_clads = [2, 4]
        w_cores = [ i/10.0 for i in range(2, 11) ]

        aspect = float(nx) / ny
        dim_x = math.ceil(math.sqrt(len(w_cores) / aspect))
        dim_y = math.ceil(float(len(w_cores))/dim_x)

        for t_core in t_cores:
            for t_l_clad, t_u_clad in itertools.product(t_l_clads, t_u_clads):
                variables.setvariable('t_clad_u', t_u_clad)
                variables.setvariable('t_clad_d', t_l_clad)

                # generate a list of y_offsets to try
                max_offset = (t_l_clad - t_u_clad)/2.0
                if max_offset == 0:
                    offsets = [0]
                else:
                    offsets = numpy.linspace(0, max_offset, 8)

                for y_offset in offsets:
                    variables.setvariable('y_offset', y_offset)

                    scatter_series = []
                    for w_core in w_cores:
                        variables.setvariable('w_core', w_core)

                        coupler.update()

                        # save the mode
                        evlist = coupler.cdev.getrhsevlist(get_ref=True)
                        evlist.list[1].profile.data.writeamf(
                            get_amf(t_core, t_u_clad, t_l_clad, y_offset, w_core))

                        # drop out of batch mode to get the scattering matrix
                        connection.toggle_mode()
                        scat_lr = pd_tools.fimm.strip_matrix(coupler.cdev.smat.lr)
                        connection.toggle_mode()

                        scatter_series.append(abs(scat_lr[0, 0]))

                    # coupling coefficients, plot and save
                    pyplot.figure(1)
                    line, = pyplot.plot(w_cores, scatter_series)
                    line.set_label('%.3f' % y_offset)

                    tup = (t_core, t_u_clad, t_l_clad, y_offset, scatter_series)
                    with open(dat_file,'a') as f:
                        f.write(repr(tup))
                        f.write('\n')

                    # modes, plot and save
                    pyplot.figure(2, (24, 24))
                    for i, w_core in enumerate(w_cores):
                        amffile = os.path.join(wd, get_amf(
                            t_core, t_u_clad, t_l_clad, y_offset, w_core))
                        data = pd_tools.fimm.load_amf(amffile)
                        ex = data['Ex']
                        pyplot.subplot(dim_y, dim_x, i+1)
                        pyplot.imshow(abs(ex))
                        pyplot.title(r'$%.1f \mu m$' % w_core)

                        #amf files take up a lot of room, so remove them
                        os.remove(amffile)
                    pyplot.savefig(
                        os.path.join(wd,
                            get_png(t_core, t_u_clad, t_l_clad, y_offset)))
                    pyplot.clf()
                pyplot.figure(1)
                pyplot.legend()
                pyplot.savefig(
                    os.path.join(wd, 'coupling-%.3f-uc%.1f-lc%.1f.png' %
                        (t_core, t_l_clad, t_u_clad)))
                pyplot.clf()

        # save the project. Doing this will allow it to close automatically
        # after we are done
        prj.savetofile(os.path.join(wd, 'ssc.prj'))

    # presumably, logging off will also close fimmprop
    os.system(r'C:\Windows\System32\logoff')
