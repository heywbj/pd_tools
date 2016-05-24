from pd_tools import PDApp

if __name__ == "__main__":
    with PDApp(host='localhost', port=5101, commit=False) as app:
        app.help()
        app.subnodes[1].help()
        app.subnodes[1].help()
        app.setwdir(r'C:\\Users')
        app.setwdir(r'D:\\Warren')

    with PDApp(host='localhost', port=5101) as app:
        app.help()
        app.subnodes[1].help()
        print(app.subnodes[1].subnodes[1].width)
        print(app.subnodes[1].subnodes[1].width)
        print(app.subnodes[1].subnodes[1].width)
        app.subnodes[1].help()
        print(app.wdir)

        app.setwdir(r'C:\\Users')

        app.setwdir(r'D:\\Warren')

