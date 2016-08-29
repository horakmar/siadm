#!/usr/bin/perl
#
################################################
# Package for communication with SPORTident HW
#
# Author:  Martin Horak
# Version: 1.0
# Date:    2. 5. 2012
#
################################################

package Sportident;

use strict;
use integer;
use Exporter 'import';
use POSIX qw(:termios_h);
use Time::HiRes qw(gettimeofday);

use Data::Dumper;

use constant WAKE => 0xff;
use constant STX => 0x02;
use constant ETX => 0x03;
use constant ACK => 0x06;
use constant NAK => 0x15;
use constant DLE => 0x10;

use constant MAX_TRIES => 5;

our @EXPORT_OK = qw(si_portdetect si_error si_dumpdata si_debug si_init si_read si_write si_parse_data si_timeout si_mktime si_handshake si_num_type si_settime);
our @EXPORT = qw(ACK NAK);

our $si_error_str = '';
our $debug = 0;
our $term;      # Termios object pointer
our %card = (); # Card data
our $ttyfh;     # Serial port filehandle
our %baudtable = (4800 => B4800, 9600 => B9600, 38400 => B38400);

#----------------------#
# Auxiliary functions  #
#----------------------#-----------------------------------
# Make time HH:MM:SS from num_of_seconds
# Hourmode: 0 ... show hours if time > 1h
#           1 ... show hours
#           2 ... only minutes
sub si_mktime {
    my $seconds = shift;
    my $hourmode = 0;
    if(scalar @_ > 0){
        $hourmode = shift;
    }
    my $n = '';
    if($seconds < 0) {
        $n = '-';
        $seconds = -$seconds;
    }
    my($hours, $minutes);
    if($hourmode < 2){
        $hours = $seconds / 3600;
        $minutes = ($seconds / 60) % 60;
    }else{
        $hours = 0;
        $minutes = ($seconds / 60);
    }
    $seconds %= 60;
    if($hours > 0 or $hourmode == 1){
        return $n . sprintf("%02d:%02d:%02d", $hours, $minutes, $seconds);
    }else{
        return $n . sprintf("%02d:%02d", $minutes, $seconds);
    }
}

# Strip off whitespace from string
sub trim($){
    my $str = $_[0];
    $str =~ s/^\s*//;
    $str =~ s/\s*$//;
    return $str;
}

# Print error status
sub si_error() { return $si_error_str; }

# Set debug level
sub si_debug($){ $debug = $_[0]; }

# Dump string data in HEX
sub si_dumpdata($){
    my $output = '';
    foreach my $i (unpack("(H2)*", $_[0])){
        $output .= "#$i";
    }
    return $output;
}

#---------------------------------#
# Port ttyUSB SI MS detection     #
#---------------------------------#------------------------
use File::Find;
use constant SI_VENDOR_ID => '10c4';
use constant SI_PRODUCT_ID => '800a';

sub si_portdetect(){
    my @si_ttys = ();
    my $wanted = sub {
        if(/^ttyUSB/){
            my $dir = substr($File::Find::dir, 0, rindex($File::Find::dir, '/'));
            if(open(V, '<', "$dir/idVendor") && open(P, '<', "$dir/idProduct")){
                my $v = <V>; my $p = <P>; chomp($v, $p);
                push(@si_ttys, "/dev/$_") if($v eq SI_VENDOR_ID && $p eq SI_PRODUCT_ID);
                close V; close P;
            }
        }
    };
    find($wanted, '/sys/devices');
    return @si_ttys;
}

#---------------------------------#
# Serial port (TTY) manipulation  #
#---------------------------------#------------------------
# Set speed of serial port
sub si_setspeed($) {
    my($baud) = $_[0];
    $baud = (defined($baudtable{$baud})) ? $baudtable{$baud} : B38400;
    $term->setispeed($baud);
    $term->setospeed($baud);
    $term->setattr($ttyfh, TCSANOW);
    print ">>> Port speed set to $_[0].\n" if($debug > 3);
}

# Set timeout for TTY read in 1/10 sec
sub si_timeout($) {
    my($time) = $_[0];
    $term->setcc(VTIME, $time);
    $term->setattr($ttyfh, TCSANOW);
}

# Setup terminal settings
sub setup_tty($) {
    my $serialport = $_[0];
    unless(open(TTY, "+<", $serialport)){
        $si_error_str = "Cannot open $serialport. $!";
        return undef;
    }
    my $ttyfh = fileno(TTY);
    $term = POSIX::Termios->new();  # Global
    $term->getattr($ttyfh);

    my $flag = $term->getlflag(); # Local flags
    $flag &= ~(ECHO | ECHOK | ICANON | ISIG);
    $term->setlflag($flag);

    $flag = $term->getiflag(); # Input flags
    $flag &= ~(BRKINT | ICRNL | IGNCR | INLCR | INPCK | ISTRIP | IXOFF | IXON | PARMRK);
    $term->setiflag($flag);
    
    $flag = $term->getoflag(); # Output flags
    $flag &= ~OPOST;
    $term->setoflag($flag);

    $term->setcc(VTIME, 1); # Set VTIME to 0.1 seconds
    $term->setcc(VMIN, 0); # Return immediately if byte received
    $term->setispeed(B38400); # Set output to 38400
    $term->setospeed(B38400); # Set output to 38400
    $term->setattr($ttyfh, TCSANOW); # Set the termio attributes
    if($debug > 3){
        print ">>> Serial port $serialport settings:\n";
        system("stty -a < $serialport"); # Display terminal settings
    }
    return $ttyfh;
} # End of SetupTerm

#--------------------------------#
# SI lowlevel data manipulation  #
#--------------------------------#-------------------------
# CRC computation
sub si_crc(@) {
	my $Polynom = 0x8005;
	my $Bitmask = 0x8000;
	my $Intmask = 0xFFFF;

	my($length, @data) = @_;
	my $sum; my $sum1;
	my $p = 0;

	return 0 if($length < 2);
	$sum = $data[$p++];
	$sum = ($sum << 8) + $data[$p++];

	return $sum if($length == 2);

	for(my $i = ($length >> 1); $i > 0; $i--){
		if($i > 1){
			$sum1 = $data[$p++];
			$sum1 = (($sum1 << 8) & $Intmask) + $data[$p++];
		}else{
			if($length & 1){
				$sum1 = $data[$p++];
				$sum1 = $sum1 << 8
			}else{
				$sum1 = 0;
			}
		}

		foreach my $k (0 .. 15){
			if($sum & $Bitmask){
				$sum = ($sum << 1) & $Intmask;
				$sum = ($sum + 1) & $Intmask if($sum1 & $Bitmask);
				$sum ^= $Polynom;
			}else{
				$sum = ($sum << 1) & $Intmask;
				$sum = ($sum + 1) & $Intmask if($sum1 & $Bitmask);
			}
			$sum1 = ($sum1 << 1) & $Intmask;
		}
	}
	return $sum;
}

# Convert data to output string, adding frame, DLE or crc
sub si_frame(@) {
    my @indata = @_;
    my @outdata;
    my $command = $indata[0];
    {
        if($command < 0x20){                     # Control codes
            @outdata = (WAKE, $command);
            last;
        }
        if($command < 0x80 || $command == 0xc4){ # Old protocol
            @outdata = (WAKE, STX);
            foreach my $i (@indata){
                push(@outdata, DLE) if($i < 0x20);
                push(@outdata, $i);
            }
            push(@outdata, ETX);
            last;
        }
                                                 # New protocol
        my $len = $indata[1];
        my $crc = si_crc($len+2, @indata);
        @outdata = (WAKE, STX, @indata, ($crc >> 8), ($crc & 0xff), ETX);
    }
    return pack("C*", @outdata);
}

# Convert input string to data, striping communication frame, decoding DLE or crc checking
sub si_unframe($) {
    my @indata = unpack("C*", $_[0]);
    my @outdata;
    my $i;
    while(defined($i = shift(@indata))){
        if($i == NAK){
            return NAK;
        }
        if($i == ACK){
            return ACK;
        }
        if($i == STX){
            last;
        }
    }
    unless(defined($i) && $i == STX){
        print "Read error> Unrecognized input data.\n" if($debug > 2);
        $si_error_str = "Unrecognized input data.";
        return ();
    }
    # STX found
    my $command = $indata[0];
    if($command < 0x80 || $command == 0xc4){ # Old protocol
        my $f_dle = 0;
        foreach my $i (@indata){             # Strip off DLE
            if($f_dle > 0){
                $f_dle = 0;
            }elsif($i == ETX){
                last;
            }elsif($i == DLE){
                $f_dle++;
                next;
            }
            push(@outdata, $i);
        }
    }else{                                   # New protocol
        my $len = $indata[1];
        my $data_crc = ($indata[$len+2] << 8) + $indata[$len+3];
        my $comp_crc = si_crc($len+2, @indata);
        if($comp_crc ne $data_crc){
            print "Read error> Bad CRC.\n";
            $si_error_str = "Bad CRC.";
            return ();
        }
        @outdata = @indata[0..$len+2];
    }
    return @outdata;
}

#-------------------#
# SI communication  #
#-------------------#--------------------------------------------
# Read from SI station
sub si_read(\@) {
    my $p_data = shift;
    my $Buff = '';
    my $Chunk = 256;
    my $BytesRead = sysread(TTY, $Buff, $Chunk, 0); # Read bytes into Buff
    unless(defined($BytesRead)) {
        $si_error_str = "sysread() error: $!";
        return undef;
    }
    print ">> <i< " , si_dumpdata($Buff), "\n" if($debug > 2);
    @$p_data = si_unframe($Buff);
    return scalar @$p_data;
}

# Write to SI station
sub si_write(@) {
    my $Buff = si_frame(@_);
    my $BytesWrt = syswrite(TTY, $Buff);
    unless(defined($BytesWrt)){
        $si_error_str = "syswrite() error: $!";
        return undef;
    }
    print ">> >o> " , si_dumpdata($Buff), "\n" if($debug > 2);
    return $BytesWrt;
}

sub si_handshake {
    my $data_write = shift;
    my $data_read = shift;
    my $tries = shift;
    $tries = MAX_TRIES unless(defined $tries);
    while($tries > 0){
        si_write(@$data_write);
        if(si_read(@$data_read) && $data_read->[0] != NAK){
            return scalar @$data_read;
        }
        $tries--;
        sleep 1;
    }
    return 0;
}

sub si_settime(@){
    my @timestart = gettimeofday();
    my @time_p;
    if(scalar @_ == 2){
        @time_p = @_;
    }else{
        @time_p = gettimeofday();
    }
    my $tries = MAX_TRIES;
    my @time;
    while($tries > 0){
        my @timestop = gettimeofday();
        $time[0] = $time_p[0] + $timestop[0] - $timestart[0];
        $time[1] = $time_p[1] + $timestop[1] - $timestart[1];
        if($time[1] > 1000000){
            $time[0]++;
            $time[1] -= 1000000;
        }elsif($time[1] < 0){
            $time[0]--;
            $time[1] += 1000000;
        }
        my @timevals = localtime($time[0]);
        my $pm = 0;
        my $secs = $timevals[2]*3600 + $timevals[1]*60 + $timevals[0];
        if($secs > 43200){
            $secs -= 43200;
            $pm = 1;
        }
        my $td = ($timevals[6] << 1) + $pm;
        my $tss = int($time[1]*256/1000000);
        my @command = (0xF6, 0x07, $timevals[5]-100, $timevals[4]+1, $timevals[3], $td, ($secs >> 8) & 0xFF, $secs & 0xFF, $tss);
        si_write(@command);
        my @data_read;
        if(si_read(@data_read) && $data_read[0] != NAK){
            return 1;
        }
        $tries--;
        sleep 1;
    }
    return 0;
}


# Initialization of serial communication, TTY speed setting, master station detect procedure
# Returns: Serial port filehandle
sub si_init {
    my $serialport = shift;
    my $ms = shift;             # Master station options
    unless(-c $serialport && -r $serialport){
        $si_error_str = "Cannot read from $serialport.\n";
        return undef;
    }
    unless(defined($ttyfh = setup_tty($serialport))){ return undef; }
    si_timeout(2);
    my $ms_type; my $ms_cn; my $ms_speed = 38400;  # Master station
    TTYtest:{
        si_write(0xf0, 0x01, 0x4d);
        my @data = ();
        my $count = si_read(@data);
        die si_error() unless(defined($count));
        if($count == 0){    # no answer
            if($ms_speed == 38400){       # Try less speed
                $ms_speed = 4800;
                si_setspeed($ms_speed);
                redo TTYtest;
            }else{
                $si_error_str = "No communication with SI MS on $serialport.\n";
                return undef;
            }
        }else{              # some answer
            if($data[0] != NAK){
                $ms_cn = ($data[2] << 8) | $data[3];
                $ms_type = 1;       # Newer
                if(defined($ms)){
                    si_write(0x83,0x02,0x74,0x01);      # Get protocol information
                    si_read(@data);
                    if($data[0] != NAK){
                        my $cpc = $data[5];
                        $$ms{cpc} = $cpc;
                        $$ms{extprot} = $cpc & 0x01;
                        $$ms{autosend} = ($cpc >> 1) & 0x01;
                        $$ms{handshake} = ($cpc >> 2) & 0x01;
                        $$ms{password} = ($cpc >> 4) & 0x01;
                        $$ms{punch} = ($cpc >> 7) & 0x01;
                    }
                }
            }else{          # try older protocol
                si_write(0x70, 0x4d);
                $count = si_read(@data);
                die si_error() unless(defined($count));
                if($count == 0 || $data[0] == NAK){
                    $si_error_str = "SI MS not recognized.\n";
                    return undef;
                }else{
                    $ms_type = 0;   # Older
                    $ms_cn = $data[1];
                }
            }
        }
    }
    if(defined($ms)){
        $$ms{type} = $ms_type;
        $$ms{cn} = $ms_cn;
        $$ms{speed} = $ms_speed;
    }
    return $ttyfh;
}


#----------------------------------#
# High level SI data manipulation  #
#----------------------------------#-----------------------
# Parse 4 byte punch data (SI 6/8/9/p)
sub si_mkpunch4(\%$@){
    my $p_control = shift;
    my($subsec, $ptd, $cn, $time1, $time0) = @_;
    my $time = ($time1 << 8) | $time0;
    $time += 43200 if(($ptd & 0x01) > 0);     # PM
    my $milisec = 0;
    if($subsec > 0) {
        $milisec = $cn * 1000 / 256;
        $cn = 0;
    }else{
        $cn = $cn + ((($ptd >> 6) & 0x03) << 8);
    }
    my $dow = ($ptd >> 1) & 0x07;
    if($dow == 7){                  # No valid data
        ($time, $cn, $milisec) = (0, 0, 0);
        $$p_control{null} = 1;
    }else{
        $$p_control{null} = 0;
    }
    $$p_control{time} = $time;
    $$p_control{cn} = $cn;
    $$p_control{milisec} = $milisec;
    $$p_control{dow} = $dow;
}

# Parse 3 byte punch data (SI 5)
sub si_mkpunch3(\%@){
    my $p_control = shift;
    my($cn, $time1, $time0, $start) = @_;
    $$p_control{cn} = $cn;
    $$p_control{time} = ($time1 << 8) + $time0;
    $$p_control{time} += 43200 if($$p_control{time} < $start);
}

# Detect null data (for SI 5)
sub detectnull(\%){
    my $p_control = shift;
    $$p_control{null} = ($$p_control{time} == 0xEEEE) ? 1 : 0;
}

# Get information from SI card data
sub si_parse_data(\%\@$) {
    my $p_card = shift;
    my $p_data = shift;
    my $start = shift;
    my $card_type;
    print ">>> Start = $start\n" if($debug > 2);
    %$p_card = ();
    CARD:{ 
        if($$p_data[7] == 0xED){        # SI card 6
            ($$p_card{id}, $$p_card{type}) = si_num_type(@$p_data[10..13]);
            $$p_card{surname} = trim(pack("C*", @$p_data[48..67]));
            $$p_card{firstname} = trim(pack("C*", @$p_data[68..87]));
            $$p_card{count} = $$p_data[0x12];
            si_mkpunch4(%{$$p_card{start}}, 0, @$p_data[24..27]);
            si_mkpunch4(%{$$p_card{finish}}, 0, @$p_data[20..23]);
            si_mkpunch4(%{$$p_card{check}}, 0, @$p_data[28..31]);
#            si_mkpunch4(%{$$p_card{clear}}, 0, @$p_data[32..35]);
#            si_mkpunch4(\%{$$p_card{last}}, 0, @$p_data[36..39]);

            for(my $i = 0; $i < $$p_card{count}; $i++){        # Control data
                my $offset = 0x80 + 4 * $i;
                si_mkpunch4(%{$$p_card{punches}[$i]}, 0, @$p_data[$offset..$offset+3]);
            }
            last;
        }
        if($$p_data[7] == 0xEA){        # SI card 8+
            ($$p_card{id}, $$p_card{type}) = si_num_type(@$p_data[24..27]);
            $$p_card{count} = $$p_data[0x16];
            si_mkpunch4(%{$$p_card{check}}, 0, @$p_data[8..11]);
            si_mkpunch4(%{$$p_card{start}}, 0, @$p_data[12..15]);
            si_mkpunch4(%{$$p_card{finish}}, 0, @$p_data[16..19]);
            my $card_series = $$p_data[0x18] & 0xF;
            my $punches_offset = 0;
            SERIES:{
                $punches_offset = 0x38, last if($card_series == 1);     # SI 9
                $punches_offset = 0x88, last if($card_series == 2);     # SI 8
                $punches_offset = 0xB0, last if($card_series == 4);     # SI p
                $punches_offset = 0x80, last if($card_series == 15);    # SIAC1
            }
            die "Unknown card series.\n" if($punches_offset == 0);
            for(my $i = 0; $i < $$p_card{count}; $i++){        # Control data
                my $offset = $punches_offset + 4 * $i;
                si_mkpunch4(%{$$p_card{punches}[$i]}, 0, @$p_data[$offset..$offset+3]);
            }
            last;
        }
        # SI card 5
        ($$p_card{id}, $$p_card{type}) = si_num_type(0,$$p_data[6],@$p_data[4..5]);
        $$p_card{count} = $$p_data[0x17] - 1;
		$$p_card{check}{time} = ($$p_data[0x19] << 8) + $$p_data[0x1A];
        $$p_card{start}{time} = ($$p_data[0x13] << 8) + $$p_data[0x14];
		$$p_card{finish}{time} = ($$p_data[0x15] << 8) + $$p_data[0x16];
        detectnull(%{$$p_card{check}});
        detectnull(%{$$p_card{start}});
        detectnull(%{$$p_card{finish}});
        # AM/PM detect heuristic
        $$p_card{check}{time} += 43200 if($$p_card{check}{time} < $start);
        $$p_card{start}{time} += 43200 if($$p_card{start}{time} < $start);
        $$p_card{finish}{time} += 43200 if($$p_card{finish}{time} < $start);

        $$p_card{check}{time} = 0 if($$p_card{check}{null});
        $$p_card{start}{time} = 0 if($$p_card{start}{null});
        $$p_card{finish}{time} = 0 if($$p_card{finish}{null});
        for(my $i = 0; $i < $$p_card{count}; $i++){        # Control data
            my $offset;
            if($i > 29){   # Last six punches without time
                $offset = 0x20 + ($i - 30) * 0x10;
                $$p_card{punches}[$i]{cn} = $$p_data[$offset];
            }else{
                $offset = 0x21 + 3 * $i + $i / 5;
                si_mkpunch3(%{$$p_card{punches}[$i]}, @$p_data[$offset..$offset+2], $start);
            }
        }
        last;
    }
} # End of si_parse_data

sub si_num_type{
    my @si = @_;
    my $type = 0;
    my $num = 0;
    $si[1] = 0 if($si[1] == 1);
    if($si[1] <= 4){
        $num = 100000 * $si[1] + ($si[2] << 8) + $si[3];
        $type = 5;
    }else{
        $num = ($si[1] << 16) + ($si[2] << 8) + $si[3];
        {
        if($num < 1000000){
            $type = 6;
            last;
        }
        if($num < 2000000){
            $type = 9;
            last;
        }
        if($num < 3000000){
            $type = 8;
            last;
        }
        if($num > 4000000 && $num < 5000000){
            $type = 20; # pCard
            last;
        }
        if($num > 6000000 && $num < 7000000){
            $type = 21; # tCard
            last;
        }
        if($num > 7000000 && $num < 8000000){
            $type = 10;
            last;
        }
        if($num > 8000000 && $num < 9000000){
            $type = 30; # SIAC1
            last;
        }
        if($num > 9000000 && $num < 10000000){
            $type = 11;
            last;
        }
        if($num > 14000000 && $num < 15000000){
            $type = 22; # fCard
            last;
        }
        if($num > 16711680 && $num <= 16777215){
            $type = 26;
            last;
        }
        }
    }
    return($num, $type);
}
1;
