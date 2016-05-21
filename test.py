from pd_tools import PDApp

if __name__ == "__main__":
    with PDApp() as app:
        app.help()
        app.subnodes[1].help()

    pdApp1 = PDApp()
    pdApp2 = PDApp()
    pdApp1.connect()
    print(pdApp1.exc('help app.wdir'))
    pdApp1.disconnect()
    pdApp2.connect()
    print(pdApp2.exc('help app.subnodes'))
    pdApp2.disconnect()

