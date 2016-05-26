"""convenience functions for fimmwave"""

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


def add_rwg(node, idx, name, slice_specs):
    node.addsubnode('rwguideNode', name)
    wg = node.subnodes[idx]

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
            l.size = spec['size']
            l.nr11 = l.nr22 = l.nr33 = spec['nr']

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
        shape.xposn = shapespec['x']
        shape.yposn = shapespec['y']
        shape.width = shapespec['width']
        shape.height = shapespec['height']
        shape.nr11 = shape.nr22 = shape.nr33 = shapespec['nr']

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

        else:
            raise NotImplementedError(
                'unrecognized element type %s' % repr(elspec['type']))

    return dev, comp
