%define keepstatic 1

Name:       zlib
Summary:    The zlib compression and decompression library
Version:    1.2.8
Release:    0
Group:      System/Libraries
License:    Zlib
URL:        http://www.gzip.org/zlib/
Source0:    http://www.zlib.net/zlib-%{version}.tar.gz
Source1001:     packaging/zlib.manifest
Requires(post): /sbin/ldconfig
Requires(postun): /sbin/ldconfig
BuildRequires:  automake
BuildRequires:  autoconf
BuildRequires:  libtool

%description
Zlib is a general-purpose, patent-free, lossless data compression
library which is used by many different programs.

%package -n minizip
Summary:    Minizip manipulates files from a .zip archive
Group:      System/Libraries
Requires:   %{name} = %{version}-%{release}
Requires(post): /sbin/ldconfig
Requires(postun): /sbin/ldconfig

%description -n minizip
Minizip manipulates files from a .zip archive.

%package -n minizip-devel
Summary:    Development files for the minizip library
Group:      Development/Libraries
Requires:   %{name} = %{version}-%{release}

%description -n minizip-devel
This package contains the libraries and header files needed for
developing applications which use minizip.

%package devel
Summary:    Header files and libraries for Zlib development
Group:      Development/Libraries
Requires:   %{name} = %{version}-%{release}

%description devel
The zlib-devel package contains the header files and libraries needed
to develop programs that use the zlib compression and decompression
library.



%prep
%setup -q -n %{name}-%{version}
cp %{SOURCE1001} .

mkdir contrib/minizip/m4
cp minigzip.c contrib/minizip
iconv -f windows-1252 -t utf-8 <ChangeLog >ChangeLog.tmp
mv ChangeLog.tmp ChangeLog

%build
CFLAGS=$RPM_OPT_FLAGS ./configure --libdir=%{_libdir} --includedir=%{_includedir} --prefix=%{_prefix}

#ensure 64 offset versions are compiled (do not override CFLAGS blindly)
%ifarch %{arm}
export CFLAGS="`egrep ^CFLAGS Makefile | sed -e 's/CFLAGS=//' | sed -e 's/vfpv3/neon/' | sed -e 's/neon-d16/neon/'` -D__ARM_HAVE_NEON"
export SFLAGS="`egrep ^SFLAGS Makefile | sed -e 's/SFLAGS=//' | sed -e 's/vfpv3/neon/' | sed -e 's/neon-d16/neon/'` -D__ARM_HAVE_NEON"
%else
export CFLAGS="`egrep ^CFLAGS Makefile | sed -e 's/CFLAGS=//'`"
export SFLAGS="`egrep ^SFLAGS Makefile | sed -e 's/SFLAGS=//'`"
%endif

#
# first,build with -fprofile-generate to create the profile data
#
make %{?_smp_mflags} CFLAGS="$CFLAGS -pg -fprofile-generate" SFLAGS="$SFLAGS -pg -fprofile-generate"

#
# Then run some basic operations using the minigzip test program
# to collect the profile guided stats
# (in this case, we compress and decompress the content of /usr/bin)
#
cp Makefile Makefile.old
make test -f Makefile.old LDFLAGS="libz.a -lgcov"
cat /usr/bin/* | ./minigzip | ./minigzip -d &> /dev/null

#
# Now that we have the stats, we need to build again, using -fprofile-use
# Due to the libtool funnies, we need to hand copy the profile data to .libs
#
make clean
mkdir .libs
#cp *gcda .libs

#
# Final build, with -fprofile-use
#
make %{?_smp_mflags} CFLAGS="$CFLAGS -fprofile-use"  SFLAGS="$SFLAGS -fprofile-use"  


cd contrib/minizip
%reconfigure
make %{?_smp_mflags}

%install
rm -rf ${RPM_BUILD_ROOT}
%make_install

mkdir $RPM_BUILD_ROOT/%{_lib}
mv $RPM_BUILD_ROOT%{_libdir}/libz.so.* $RPM_BUILD_ROOT/%{_lib}/

reldir=$(echo %{_libdir} | sed 's,/$,,;s,/[^/]\+,../,g')%{_lib}
oldlink=$(readlink $RPM_BUILD_ROOT%{_libdir}/libz.so)
ln -sf $reldir/$(basename $oldlink) $RPM_BUILD_ROOT%{_libdir}/libz.so

pushd contrib/minizip
make install DESTDIR=$RPM_BUILD_ROOT
popd

rm -f $RPM_BUILD_ROOT%{_libdir}/*.la

mkdir -p %{buildroot}/%{_datadir}/license
cp -f COPYING %{buildroot}%{_datadir}/license/%{name}
cp -f COPYING %{buildroot}%{_datadir}/license/minizip

#%check
#make test


%post -p /sbin/ldconfig

%postun -p /sbin/ldconfig


%post -n minizip -p /sbin/ldconfig

%postun -n minizip -p /sbin/ldconfig


%docs_package

%files
%manifest %{name}.manifest
/%{_lib}/libz.so.*
%{_datadir}/license/%{name}

%files -n minizip
%manifest %{name}.manifest
%{_libdir}/libminizip.so.*
%{_libdir}/libz.a
%{_datadir}/license/minizip

%files -n minizip-devel
%manifest %{name}.manifest
%dir %{_includedir}/minizip
%{_includedir}/minizip/*.h
%{_libdir}/libminizip.so
%{_libdir}/libminizip.a
%{_libdir}/pkgconfig/minizip.pc

%files devel
%manifest %{name}.manifest
%{_libdir}/libz.so
%{_includedir}/zconf.h
%{_includedir}/zlib.h
%{_libdir}/pkgconfig/zlib.pc

