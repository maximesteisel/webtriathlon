
exe\01python-2.7.12.msi
exe\pygtk-all-in-one-2.24.2.win32-py2.7.msi
exe\pywin32-219.win32-py2.7.exe

C:\Python27\python.exe -m pip install --upgrade pip==20.3.4 --trusted-host pypi.python.org --trusted-host pypi.org --trusted-host files.pythonhosted.org
C:\Python27\python.exe -m pip install --trusted-host pypi.python.org --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
