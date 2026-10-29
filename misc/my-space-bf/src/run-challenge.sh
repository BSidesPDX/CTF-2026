#!/usr/bin/env bash
/usr/bin/socat TCP4-LISTEN:22333,reuseaddr,fork EXEC:"./bf.sh",pty,echo=0

