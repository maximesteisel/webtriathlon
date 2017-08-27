#!/bin/bash

HEADER="#!/usr/bin/python\n"

mkdir -p build
function build  {
    echo "building $1.$2"
    cd src/$1
    #python -m compileall .
    git rev-list --count HEAD > REVNO
    zip -r  ../../build/$1.zip *  -x@../../.gitignore
    cd ../../build
    echo -e $HEADER| cat - $1.zip > $1.$2
    rm $1.zip
    chmod +x $1.$2
    cd ..
}

build server py
build encoder py
