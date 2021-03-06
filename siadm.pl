#!/usr/bin/perl -w
#
###########################################
# SI control administration
#
# Author:   Martin Horak
# Version:  1.1
# Date:     23. 9. 2018
#
###########################################

# Uncomment after installing
#use lib "$ENV{HOME}/lib";
use lib ".";

use strict;
use Sportident qw(si_debug si_read si_write si_timeout si_init ACK NAK si_portdetect si_handshake si_mktime si_settime);
use POSIX qw(:termios_h);
use Time::HiRes qw(gettimeofday usleep);

# use constant MAX_TRIES => 5;

## Variables ## ============================
############### ============================
our $test = 0;
our $verbose = 1;
our $serial = '';
our $local = 0;
our @commands = ();
our @weekdays = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat');
our @station_modes = ('Undef', 'Undef', 'Control', 'Start', 'Finish', 'Readout', 'Undef', 'Clear', 'Undef', 'Undef', 'Check');
our $max_tries = 5;     # Only for settime();

## Functions ## ============================
############### ============================
sub DoCMD{
    my $command = shift;
    print $command, "\n" if($verbose > 1);
    if($test == 0){
        my $err = qx/$command 2>&1/;
        print "Chyba: $err\n" if($? != 0);
    }
}

## Usage ## --------------------------------
sub Usage {
    my $script_name = substr($0, rindex($0, '/')+1);
    print <<"EOF";

Usage:
    $script_name [-h] [-tvql] -s <tty> command [params]

Setup of SI stations

Parameters:
    -h  ... help
    -t  ... test - dry run, do not execute commands
    -v  ... verbose - more information
    -q  ... quiet - less information
    -l  ... communicate to local (master) SI station
    -s <tty>   ... serial port to read from [autodetected]

Commands:
    off    ... turn off
    beep   ... make beep
    rtime  ... read time
    wtime  ... write time (localtime of computer)
    rprot  ... read protocol info
    wprot <ep>,<as> ... write protocol info
        ep ... extended protocol [0/1]
        as ... autosend [0/1]
    rcn    ... read control mode and number
    wcn <mode>,<number> ... write control mode and number
        modes ... [Control, Start, Finish, Readout, Clear, Check]
    batst  ... battery status (capacity left in %)
    fwvers ... firmware version

EOF
    exit 1;
}
## Usage end ## ----------------------------

sub setremote(){
    my @data;
    my @command = (0xF0,0x01,0x53);
    return si_handshake(\@command, \@data);
}

sub turnoff(){
    my @data;
    my @command = (0xF8,0x01,0x60);
    return si_handshake(\@command, \@data);
}

sub gettime(){
    my @data;
    my @command = (0xF7,0x00);
    if(si_handshake(\@command, \@data)){
        my $td = $data[7];
        my $weekday = ($td >> 1) & 0x07;
        my $pm = $td & 0x01;
        my $secs = ($data[8] << 8) + $data[9] + $pm * 43200;
        my $time = si_mktime($secs);
        my $subsec = $data[10] * 1000 / 256;
        return sprintf("%s, %2d. %2d. 20%2d, %s,%03d", $weekdays[$weekday], $data[6], $data[5], $data[4], $time, $subsec);
    }
    return '';
}

sub readcn(){
    my @data;
    my @command = (0x83,0x02,0x71,0x02);
    if(si_handshake(\@command, \@data)){
        return($station_modes[$data[5]], $data[6]);
    }else{
        return 0;
    }
}

sub readfwversion(){
    my @data;
    my @command = (0x83,0x02,0x05,0x03);
    if(si_handshake(\@command, \@data)){
        return(chr($data[5]) . chr($data[6]) . chr($data[7]));
    }else{
        return 0;
    }
}

sub readbatstate(){
    my @data;
    my $result = 0;
    READ: {
        my @command = (0x83,0x02,0x34,0x04);
        last READ unless(si_handshake(\@command, \@data));
        last READ if($data[5] == 0xFF);
        my $consumed = (($data[5] << 24) + ($data[6] << 16) + ($data[7] << 8) + $data[8]) / 3600;
        print ">>> Consumed: $consumed mAh\n" if($verbose > 2);
        @command = (0x83,0x02,0x18,0x04);
        last READ unless(si_handshake(\@command, \@data));
        my $capacity = (($data[5] << 24) + ($data[6] << 16) + ($data[7] << 8) + $data[8]) / 3600;
        print ">>> Capacity: $capacity mAh\n" if($verbose > 2);
        $result = int(100 * (1 - $consumed/$capacity));
    }
    return $result;
}

sub readbatvoltage(){
    my @data;
    my $result = 0;
    READ: {
        my @command = (0x83,0x02,0x50,0x02);
        last READ unless(si_handshake(\@command, \@data));
        my $voltage = ($data[5] << 8) + $data[6];
        print ">>> Voltage value: $voltage\n" if($verbose > 2);
        $voltage /= 131 if($voltage > 13100);
        $result = $voltage / 100;
    }
    return $result;
}

sub readbattemp(){
    my @data;
    my $result = 0;
    READ: {
        my @command = (0x83,0x02,0x52,0x02);
        last READ unless(si_handshake(\@command, \@data));
        my $temper = ($data[5] << 8) + $data[6];
        print ">>> Temperature value: $temper\n" if($verbose > 2);
        if($temper >= 25800) {
            $result = ($temper - 25800) / 92;
        }else{
            $result = $temper / 10;
        }
    }
    return $result;
}

sub readbatdate(){
    my @data;
    my $result = '';
    READ: {
        my @command = (0x83,0x02,0x15,0x03);
        last READ unless(si_handshake(\@command, \@data));
        if($data[5] < 80){
            $data[5] += 2000;
        }else{
            $data[5] += 1900;
        }
        $result = "$data[7].$data[6].$data[5]";
    }
    return $result;
}

sub beep($){
    my $beeps = $_[0];
    my @data;
    my @command = (0xF9,0x01,$beeps);
    return si_handshake(\@command, \@data);
}

## Main ## =================================
########## =================================

## Getparam ## -----------------------------
my $a;
GetP: while(defined($a = shift)){
    if(substr($a, 0, 1) eq '-'){
        my @aa = split(//, $a);
        shift @aa;
        foreach my $i (@aa){
            if($i eq 'h'){ &Usage(); next; };
            if($i eq 't'){ $test = 1; next; };
            if($i eq 'v'){ $verbose++; next; };
            if($i eq 'q'){ $verbose--; next; };
            if($i eq 's'){ $serial = shift; next; };
            if($i eq 'l'){ $local = 1; next; };
        }
    }else{
        push(@commands, $a);
    }
}


## Getparam end ## -------------------------

if($serial eq ''){
    my @det_serials = si_portdetect();
    die "SI Master station not detected, try option -s.\n" if(scalar @det_serials == 0);
    $serial = $det_serials[0];
    print ">> Detected SI harware on $serial.\n" if($verbose > 2);
}

si_debug($verbose);
my $ttyfh = si_init($serial);
si_timeout(20);

if($local == 0){
    die "Cannot set remote mode.\n" unless setremote();
}
while(my $command = shift(@commands)){
    my @data = ();
    if($command eq 'batst'){
        my $batst = readbatstate();
        if($batst == 0){
            print "Battery status not available.\n";
        }else{
            print "Battery status: $batst %\n";
        }
        my $batvoltage = readbatvoltage();
        printf("Battery voltage: %.2f V\n", $batvoltage);
        my $battemp = readbattemp();
        printf("Battery temperature: %.2f °C\n", $battemp);
        my $batdate = readbatdate();
        print "Battery date: $batdate\n";
        next;
    }
    if($command eq 'off'){
        print "Cannot turn off.\n" unless turnoff();
        next;
    }
    if($command eq 'fwvers'){
        my $fwversion = readfwversion();
        if($fwversion == 0){
            print "Firmware version cannot be read.\n";
        }else{
            print "Firmware version: $fwversion\n";
        }
        next;
    }
    if($command eq 'rprot'){
        my @cmd = (0x83,0x02,0x74,0x01);
        if(si_handshake(\@cmd, \@data)){
            my $cpc = $data[5];
            my $a;
            $a = (($cpc & 0x01) > 0) ? "Yes" : "No";
            print "Extended protocol ... $a\n";
            $a = (($cpc & 0x02) > 0) ? "Yes" : "No";
            print "Auto send         ... $a\n";
            $a = (($cpc & 0x04) > 0) ? "Yes" : "No";
            print "Handshake         ... $a\n";
            $a = (($cpc & 0x10) > 0) ? "Yes" : "No";
            print "Password set      ... $a\n";
            $a = (($cpc & 0x80) > 0) ? "Yes" : "No";
            print "Read after punch  ... $a\n";
        }else{
            print "Cannot read protocol conf.\n";
        }
        next;
    }
    if($command eq 'wprot'){
        my @cmd = (0x83,0x02,0x74,0x01); # Read protocol first
        unless(si_handshake(\@cmd, \@data)){
            print "Cannot read protocol conf.\n";
            next;
        }
        my $cpc = $data[5];

        my $p = shift(@commands);
        my ($p1,$p2) = split(',', $p);
        unless(defined $p1 && defined $p2 && ($p1 eq '0' || $p1 eq '1') && ($p2 eq '0' || $p2 eq '1')){
            print "Bad parameter for wprot.\n";
            next;
        }
        print "Write protocol: $p1, $p2\n" if($verbose > 2);
        $cpc &= ~0x01 if($p1 == 0);
        $cpc &= ~0x02, $cpc |= 0x04 if($p2 == 0);   # Clear Autosend, set Handshake 
        $cpc |=  0x01 if($p1 == 1);
        $cpc |=  0x02, $cpc &= ~0x04 if($p2 == 1);  # Set Autosend, clear Handshake
        @cmd = (0x82,0x02,0x74,$cpc);
        unless(si_handshake(\@cmd, \@data)){
            print "Cannot set protocol conf.\n";
        }
        next;
    }

    if($command eq 'rcn'){
        my($mode, $cn) = readcn();
        if(defined($cn)){
            print "Mode  : $mode\n";
            print "Number: $cn\n";
        }else{
            print "Cannot read control data.\n";
        }
        next;
    }

    if($command eq 'wcn'){
        my $mode_n = 0;
        my $p = shift(@commands);
        my ($mode, $cn) = split(',', $p);
        ERR:{
            PARM: {
                last unless defined($mode);
                last unless defined($cn);
                last unless($cn >= 1 && $cn <= 255 );
                last if(uc($mode) eq 'UNDEF');
                my $i = 2;
                while($i <= 10){
                    if(uc($mode) eq uc($station_modes[$i])){
                        $mode_n = $i;
                        last;
                    }
                    $i++;
                }
                last if($mode_n == 0);

                my @cmd = (0x82,0x03,0x71,$mode_n,$cn);
                if(si_handshake(\@cmd, \@data)){
                    beep(1);
                }else{
                    print "Cannot set station.\n";
                }
                last ERR;
            }
            print "Bad parameters.\n";
        }
        next;
    }

    if($command eq 'wtime'){
        if(si_settime()){
            beep(1); usleep(200000);
            $command = 'rtime';
        }else{
            print "Cannot set time.\n";
            next;
        }
    }
    if($command eq 'rtime'){
        my $time = gettime();
        my($sec, $usec) = gettimeofday();
        my @stime = localtime($sec);
        my $stime = sprintf("%s, %d. %d. %d, %d:%02d:%02d,%03d", $weekdays[$stime[6]], $stime[3], $stime[4]+1, $stime[5]+1900, $stime[2], $stime[1], $stime[0], $usec/1000);
        print "Cannot read control time.\n" if($time eq '');
        print "Control: $time\n";
        print "System:  $stime\n";
        next;
    }
    if($command eq 'beep'){
        print "Cannot beep.\n" unless beep(1);
        next;
    }
    print "Unknown command $command.\n";
}
exit;

