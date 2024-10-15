#!/usr/bin/python3

import sys

def main():
## Getparam ## -----------------------------
    argn = []
    args = sys.argv;
    i = 1
    try:
        while(i < len(args)):
            if(args[i][0] == '-'):
                for j in args[i][1:]:
                    if j == 'h':
                        Usage()
                        return
                    elif j == 'v':
                        if loglevel > 10: loglevel -= 10
                    elif j == 'q':
                        if loglevel < 50: loglevel += 10
                    elif j == 'l':
                        target = LOCAL
                    elif j == 'r':
                        target = REMOTE
                    elif j == 'f':
                        i += 1
                        logfile = args[i]
            else:
                argn.append(args[i])
            i += 1
    except IndexError:
        print("Parameter read error.")
        return

    for i in argn:
        print("{} ... {}".format(i, type(i)))


if __name__ == '__main__':
    main()

