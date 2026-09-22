import hashlib
import logging
import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from stickies.store import data_directory
from stickies.app import create_application, Controller


def main():
    directory=data_directory()
    directory.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=directory/'app.log',level=logging.WARNING,
                        format='%(asctime)s %(levelname)s %(message)s')
    app=create_application()
    name='LittlePaper-'+hashlib.sha256(str(directory).encode()).hexdigest()[:16]
    lock=QLockFile(str(directory/'app.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        socket=QLocalSocket()
        socket.connectToServer(name)
        if socket.waitForConnected(1500):
            socket.write(b'activate')
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
        return 0
    server=QLocalServer()
    QLocalServer.removeServer(name)
    server.listen(name)
    controller=Controller(app,background='--background' in sys.argv,testing='--smoke-exit' in sys.argv)
    def activate():
        connection=server.nextPendingConnection()
        if connection:
            connection.disconnectFromServer()
            connection.deleteLater()
        controller.show_manager()
    server.newConnection.connect(activate)
    def exception_hook(kind,value,tb):
        logging.error('Unhandled error',exc_info=(kind,value,tb))
        controller.error('操作未完成，错误已写入本地日志。\n'+str(value))
    sys.excepthook=exception_hook
    # Allow a bounded packaged-app smoke run without touching real user data.
    if '--smoke-exit' in sys.argv:
        QTimer.singleShot(1800,controller.quit)
    result=app.exec()
    server.close()
    lock.unlock()
    return result


if __name__=='__main__':
    sys.exit(main())
