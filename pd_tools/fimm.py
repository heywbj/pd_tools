"""convenience functions for fimmwave"""
import numpy
import re

def add_vars(node, idx, name, var_dict):
    node.addsubnode('pdVariablesNode', name)
    variables = node.subnodes[idx]
    for key, val in var_dict.items():
        variables.addvariable(key)
        variables.setvariable(key, val)

    return variables


def config_solver(node, mlp, svp):
    for key, val in mlp.items():
        setattr(node.evlist.mlp, key, val)

    for key, val in svp.items():
        setattr(node.evlist.svp, key, val)


def add_rwg(node, idx, name, slice_specs, material_db = None):
    node.addsubnode('rwguideNode', name)
    wg = node.subnodes[idx]

    if material_db:
        wg.setmaterbase(material_db)

    for i in range(len(slice_specs)):
        slice_idx = i + 1
        slice_spec = slice_specs[i]
        width = slice_spec['width']
        layer_specs = slice_spec['layers']

        # add the slices
        wg.insertslice(slice_idx)
        slyce = wg.slices[slice_idx]
        slyce.width = width

        for i in range(len(layer_specs)):
            # create the layer if necessary
            layer_idx = i + 1
            if layer_idx != 1:
                slyce.insertlayer(layer_idx)
            l = slyce.layers[layer_idx]

            # set the layer specs
            spec = layer_specs[i]

            for key, val in spec.items():
                if key == 'nr':
                    l.nr11 = l.nr22 = l.nr33 = val
                elif key == 'material':
                    l.setMAT(spec['material'])
                else:
                    setattr(l, key, val)
    return wg


def add_mwg(node, idx, name, width, height, shapespecs):
    node.addsubnode('mwguideNode', name)
    wg = node.subnodes[idx]
    wg.width = width
    wg.height = height

    for i in range(len(shapespecs)):
        shapespec = shapespecs[i]
        shape_idx = i + 1

        wg.insertshape(shape_idx, shapespec['type'])
        shape = wg.shapes[shape_idx]

        for key, val in shapespec.items():
            if key == 'nr':
                shape.nr11 = shape.nr22 = shape.nr33 = shapespec['nr']
            elif key == 'type':
                continue
            else:
                setattr(shape, key, val)

    return wg


def add_device(node, idx, name, elspecs):
    node.addsubnode('FPdeviceNode', name)
    dev = node.subnodes[idx] # FPDeviceNode
    comp = dev.cdev # FPcomponent

    for i in range(len(elspecs)):
        elspec = elspecs[i]
        elidx = i + 1

        if elspec['type'] == 'wgsect':
            # n.b. elspec['wg'] is a string. Could also pass in a wrapped
            # reference, and then we could try converting it to a fimmwave
            # 'path' of the form /Project/fiber
            comp.newwgsect(elidx, elspec['wg'], elspec['copy_molab'])

            wg = comp.eltlist[elidx]

            wg.length = elspec['length']

        elif elspec['type'] == 'sjoint':
            comp.newsjoint(elidx)
            joint = comp.eltlist[elidx]

            joint.method = elspec['method']
        else:
            raise NotImplementedError(
                'unrecognized element type %s' % repr(elspec['type']))

    return dev

def load_amf(path):
    # pattern for generic floating-point number, and generic integer
    float_p = r'[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?'
    int_p = r'[-+]?\d+'
    uint_p = r'\d+'
    bool_p = r'[01]'

    results = {}
    def append_to_results(m):
        assert m is not None
        for k,v in m.groupdict().items():
            results[k] = v

    with open(path, 'r') as f:


        # read first line
        assert f.readline().startswith('begin')

        # second line, matrix dimensions
        append_to_results(re.search(
            r'''(?P<nx>{ui})\s+
                (?P<ny>{ui})\s+
                //nxseg\ nyseg'''.format(ui=uint_p),
            f.readline(),
            re.X))

        # third line, physical dimensions
        append_to_results(re.search(
            r'''(?P<xmin>{f})\s+
                (?P<xmax>{f})\s+
                (?P<ymin>{f})\s+
                (?P<ymax>{f})\s+
                //xmin\ xmax\ ymin\ ymax'''.format(f=float_p),
            f.readline(),
            re.X))

        # fourth line, field components included
        append_to_results(re.search(
            r'''(?P<hasEX>{b})\s+
                (?P<hasEY>{b})\s+
                (?P<hasEZ>{b})\s+
                (?P<hasHX>{b})\s+
                (?P<hasHY>{b})\s+
                (?P<hasHZ>{b})\s+
                //hasEX\ hasEY\ hasEZ\ hasHX\ hasHY\ hasHZ'''.format(b=bool_p),
            f.readline(),
            re.X))

        # fifth line, propagation constant
        append_to_results(re.search(
            r'''(?P<beta_r>{f})\s+
                (?P<beta_i>{f})\s+
                //beta'''.format(f=float_p),
            f.readline(),
            re.X))

        # sixth line, wavelength
        append_to_results(re.search(
            r'''(?P<lambda>{f})\s+
                //lambda'''.format(f=float_p),
            f.readline(),
            re.X))

        # seventh line, iscomplex
        append_to_results(re.search(
            r'''(?P<iscomplex>{b})\s+
                //iscomplex'''.format(b=bool_p),
            f.readline(),
            re.X))

        # eigth line, isWGmode
        append_to_results(re.search(
            r'''(?P<isWGmode>{b})\s+
                //isWGmode'''.format(b=bool_p),
            f.readline(),
            re.X))

        # ninth line
        assert '//components follow as nyseg by nxseg matrices' in f.readline()

        # data

        iscomplex = results['iscomplex']

        header_re = re.compile(r'\s+//(?P<n>\w+) components')
        split_re = re.compile(r'\s+')
        curr_comp = None
        curr_data = None
        for line in iter(f.readline, ''):
            hm = header_re.match(line)
            if hm is not None:
                if curr_data is not None:
                    results[curr_comp] = numpy.array(curr_data).transpose()

                curr_data = []
                curr_comp = hm.groupdict()['n']
            elif line.startswith('end'):
                if curr_data is not None:
                    results[curr_comp] = numpy.array(curr_data).transpose()

                break
            else:
                assert curr_data is not None
                assert curr_comp is not None

                data = map(float, split_re.split(line.strip()))
                if iscomplex:
                    data = [complex(*pair) for pair in
                            numpy.reshape(data, (len(data)/2,2))]
                curr_data.append(data)

        return results


