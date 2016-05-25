from pd_tools import PDApp
import logging
logging.basicConfig(level=logging.DEBUG)

FIMMWAVE = r'C:\Program Files (x86)\PhotonD\Fimmwave\bin64\fimmwave.exe'

if __name__ == "__main__":
    c = PDApp(FIMMWAVE, port=5101, batch=True)
    with c as app:
        app.setwdir(r'C:\\Users')
        app.setwdir(r'D:\\Warren')
        app.addsubnode('fimmwave_prj', 'test project')

        c.toggle_mode()
        print(app.wdir)

    with PDApp(host='localhost', port=5101, batch=False) as app:
        print(app.wdir)
        print(app.subnodes[1].numsubnodes())

        app.setwdir(r'C:\\Users')

        app.setwdir(r'D:\\Warren')

