from pd_tools import PDApp

if __name__ == "__main__":
    with PDApp('localhost', 5101) as app:
        app.help()
        app.subnodes[1].help()
        print(app.subnodes[1].subnodes[1].width)
        print(app.subnodes[1].subnodes[1].width)
        print(app.subnodes[1].subnodes[1].width)
        app.subnodes[1].help()
        print(app.wdir)

        app.setwdir('C:\\')
        print(app.wdir)

        app.setwdir('D:\\Warren')
        print(app.wdir)

