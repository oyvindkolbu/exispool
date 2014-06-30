set -e

# Make sure tests are ok
python tests.py

VERSION=`python exispool.py --version |awk '{print $NF}'`

DEST=exispool-$VERSION
WWW=/hom/kolbu/www_docs/hacks/exispool
TARGZ=exispool-$VERSION.tar.gz

# Cleanup
rm -rf dist

# Fix version.
perl -pe "s/VERSION/$VERSION/g" README.tmpl > README.rst

# Make a package the python way™
python setup.py sdist

# ... though add more files :)
cd dist
tar xfz $TARGZ
mkdir -p $DEST/testspool/input/

cp ../testspool/input/1* $DEST/testspool/input/
cp ../testspool/configfile $DEST/testspool/
cp ../tests.py $DEST/


# Make new tarball.
rm $TARGZ
tar cfz $TARGZ $DEST

# Publish
cp $TARGZ $WWW/dist/
rst2html $DEST/README.rst > $WWW/index.html
cd $WWW/dist/
chmod 644 ../index.html *
ln -sf $TARGZ exispool.tar.gz

echo Husk å laste opp $DEST/index.html på \
     http://www.uio.no/tjenester/it/e-post-kalender/e-post/mer-om/software/exispool/
