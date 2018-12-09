#!/usr/bin/env perl
use 5.014;
#use warnings;

use Sportident qw(si_crc);

#my $str = "Nazdar vole";
my @str = ( 0x0a, 0x0b, 150, 150, 34, 33, 32, 10);
my $len = scalar(@str)-1;

my $crc = si_crc($len, @str);

print "Str: @str, len: $len, crc: $crc\n";
