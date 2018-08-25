./build.sh
cd build
ln -s ../installers
ln -s ../README
echo "creating release tarball"
zip -r webtriathlon-r`git rev-list --count HEAD`-db`python server.py dbversion`.zip README.*  server.py encoder.py installers
echo "cleaning up"
rm installers README
