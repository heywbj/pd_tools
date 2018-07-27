import logging

# set to loggging.DEBUG to see debugging info the stdout
logging.basicConfig(level=logging.WARNING)

import pd_tools

if __name__ == "__main__":
    # connect to Fimmwave on the default port
    hoststring = raw_input('host? [localhost] :')
    portstring = raw_input('port? [5101] :')

    host = hoststring if hoststring else 'localhost'
    port = int(portstring) if portstring else 5101

    connection = pd_tools.PDApp(host=host, port=port)
    with connection as app:
        # open interactive python shell
        try:
            from IPython import embed
            embed()
        except ImportError:
            import readline # optional, will allow Up/Down/History in the console
            import code
            variables = globals().copy()
            variables.update(locals())
            shell = code.InteractiveConsole(variables)
            shell.interact()

