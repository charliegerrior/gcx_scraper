#!/bin/bash
cd venv/lib/python3.8/site-packages/
zip -r9 ${OLDPWD}/function.zip .
cd $OLDPWD
zip -g function.zip lambda_function.py
zip -g function.zip app/*
zip -g function.zip config.py
