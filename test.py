import pd_tools

if __name__ == "__main__":
    # connect to Fimmwave on the default port
    connection = pd_tools.PDApp(host='localhost', port=5101)
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

