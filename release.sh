./build.sh
cd build
ln -s ../installers
ln -s ../README.* .
echo "creating release tarball"
zip -r webtriathlon-r`bzr revno`-db`python server.py dbversion`.zip README.*  server.py encoder.pyw installers
echo "cleaning up"
rm installers README.*.*
