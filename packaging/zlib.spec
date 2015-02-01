%define keepstatic 1

Name:       zlib
Summary:    The zlib compression and decompression library
Version:    1.2.5
Release:    2.7
Group:      System/Libraries
License:    zlib and Boost
URL:        http://www.gzip.org/zlib/
Source0:    http://www.zlib.net/zlib-%{version}.tar.gz
Patch0:     zlib-1.2.4-autotools.patch
Patch1:     zlib-1.2.5-lfs-decls-bmc-11751.patch
Requires(post): /sbin/ldconfig
Requires(postun): /sbin/ldconfig
BuildRequires:  automake
BuildRequires:  autoconf
BuildRequires:  libtool


%description
Zlib is a general-purpose, patent-free, lossless data compression
library which is used by many different programs.



%package static
Summary:    Static libraries for Zlib development
Group:      Development/Libraries
Requires:   %{name} = %{version}-%{release}

%description static
The zlib-static package includes static libraries needed
to develop programs that use the zlib compression and
decompression library.


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

# zlib-1.2.4-autotools.patch
%patch0 -p1
# zlib-1.2.5-lfs-decls-bmc-11751.patch
%patch1 -p1
mkdir contrib/minizip/m4
cp minigzip.c contrib/minizip
iconv -f windows-1252 -t utf-8 <ChangeLog >ChangeLog.tmp
mv ChangeLog.tmp ChangeLog

%build
CFLAGS=$RPM_OPT_FLAGS ./configure --libdir=%{_libdir} --includedir=%{_includedir} --prefix=%{_prefix} --arch=%{_arch}

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
cp *gcda .libs

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
cp -f COPYING %{buildroot}/%{_datadir}/license/%{name}
cp -f COPYING %{buildroot}/%{_datadir}/license/minizip

%check
make test


%post -p /sbin/ldconfig

%postun -p /sbin/ldconfig


%post -n minizip -p /sbin/ldconfig

%postun -n minizip -p /sbin/ldconfig


%docs_package

%files
/%{_lib}/libz.so.*
%{_datadir}/license/%{name}

%files static
%{_libdir}/libz.a

%files -n minizip
%{_libdir}/libminizip.so.*
%{_datadir}/license/minizip

%files -n minizip-devel
%dir %{_includedir}/minizip
%{_includedir}/minizip/*.h
%{_libdir}/libminizip.so
%{_libdir}/pkgconfig/minizip.pc

%files devel
%{_libdir}/libz.so
%{_includedir}/zconf.h
%{_includedir}/zlib.h
%{_libdir}/pkgconfig/zlib.pc

%changelog
* Fri Dec 31 2010 Yan Yin <yan.yin@intel.com> - 1.2.5
- Fix BMC #11751: incorrect large file support header in zlib package
* Thu Dec 30 2010 Yan Yin <yan.yin@intel.com> - 1.2.5
- Fix BMC #11752: optimization not used in all objects file in zlib
* Fri Jul  2 2010 Yan Yin <yan.yin@intel.com> - 1.2.5
- Upgrade to 1.2.5, drop old patches, keep profile guided optmization
* Sun Feb 14 2010 Arjan van de Ven <arjan@linux.intel.com> 1.2.3
- use profile guided optimization during the build
* Thu May  7 2009 Arjan van de Ven <arjan@linux.intel.com>
- fix for LD_AS_NEEDED=1
* Tue Jan 13 2009 Anas Nashif <anas.nashif@intel.com> 1.2.3
- Pre-Require ldconfig
* Fri Dec  5 2008 Arjan van de Ven <arjan@linux.intel.com> 1.2.3
- Minor cleanups
* Wed Feb 13 2008 Ivana Varekova <varekova@redhat.com> - 1.2.3-18
- change license tag (226671#c29)
* Mon Feb 11 2008 Ivana Varekova <varekova@redhat.com> - 1.2.3-17
- spec file changes
* Fri Nov 23 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-16
- remove minizip headers to minizip-devel
- spec file cleanup
- fix minizip.pc file
* Wed Nov 14 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-15
- separate static subpackage
* Wed Aug 15 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-14
- create minizip subpackage
* Mon May 21 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-13
- remove .so,.a
* Mon May 21 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-12
- Resolves #240277
  Move libz to /lib(64)
* Mon Apr 23 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-11
- Resolves: 237295
  fix Summary tag
* Fri Mar 23 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-10
- remove zlib .so.* packages to /lib
* Fri Mar  9 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-9
- incorporate package review feedback
  * Tue Feb 21 2007 Adam Tkac <atkac redhat com> - 1.2.3-8
- fixed broken version of libz
  * Tue Feb 20 2007 Adam Tkac <atkac redhat com> - 1.2.3-7
- building is now automatized
- specfile cleanup
* Tue Feb 20 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-6
- remove the compilation part to build section
  some minor changes
* Mon Feb 19 2007 Ivana Varekova <varekova@redhat.com> - 1.2.3-5
- incorporate package review feedback
* Mon Oct 23 2006 Ivana Varekova <varekova@redhat.com> - 1.2.3-4
- fix #209424 - fix libz.a permissions
* Wed Jul 19 2006 Ivana Varekova <varekova@redhat.com> - 1.2.3-3
- add cflags (#199379)
* Wed Jul 12 2006 Jesse Keating <jkeating@redhat.com> - 1.2.3-2
- rebuild
* Fri Feb 10 2006 Jesse Keating <jkeating@redhat.com> - 1.2.3-1.2.1
- bump again for double-long bug on ppc(64)
* Tue Feb  7 2006 Jesse Keating <jkeating@redhat.com> - 1.2.3-1.2
- rebuilt for new gcc4.1 snapshot and glibc changes
* Fri Dec  9 2005 Jesse Keating <jkeating@redhat.com>
- rebuilt
* Wed Aug 24 2005 Florian La Roche <laroche@redhat.com>
- update to 1.2.3
* Fri Jul 22 2005 Ivana Varekova <varekova@redhat.com> 1.2.2.2-5
- fix bug 163038 - CAN-2005-1849 - zlib buffer overflow
* Thu Jul  7 2005 Ivana Varekova <varekova@redhat.com> 1.2.2.2-4
- fix bug 162392 - CAN-2005-2096
* Wed Mar 30 2005 Ivana Varekova <varekova@redhat.com> 1.2.2.2-3
- fix bug 122408 - zlib build process runs configure twice
* Fri Mar  4 2005 Jeff Johnson <jbj@redhat.com> 1.2.2.2-2
- rebuild with gcc4.
* Sat Jan  1 2005 Jeff Johnson <jbj@jbj.org> 1.2.2.2-1
- upgrade to 1.2.2.2.
* Fri Nov 12 2004 Jeff Johnson <jbj@jbj.org> 1.2.2.1-1
- upgrade to 1.2.2.1.
* Sun Sep 12 2004 Jeff Johnson <jbj@redhat.com> 1.2.1.2-1
- update to 1.2.1.2 to fix 2 DoS problems (#131385).
* Tue Jun 15 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt
* Tue Mar  2 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt
* Fri Feb 13 2004 Elliot Lee <sopwith@redhat.com>
- rebuilt
* Sun Jan 18 2004 Jeff Johnson <jbj@jbj.org> 1.2.1.1-1
- upgrade to zlib-1.2.1.1.
* Sun Nov 30 2003 Florian La Roche <Florian.LaRoche@redhat.de>
- update to 1.2.1 release
* Mon Oct 13 2003 Jeff Johnson <jbj@jbj.org> 1.2.0.7-3
- unrevert zlib.h include constants (#106291), rejected upstream.
* Wed Oct  8 2003 Jeff Johnson <jbj@jbj.org> 1.2.0.7-2
- fix: gzeof not set when reading compressed file (#106424).
- fix: revert zlib.h include constants for now (#106291).
* Tue Sep 23 2003 Jeff Johnson <jbj@redhat.com> 1.2.0.7-1
- update to 1.2.0.7, penultimate 1.2.1 release candidate.
* Tue Jul 22 2003 Jeff Johnson <jbj@redhat.com> 1.2.0.3-0.1
- update to release candidate.
* Wed Jun  4 2003 Elliot Lee <sopwith@redhat.com>
- rebuilt
* Mon May 19 2003 Jeff Johnson <jbj@redhat.com> 1.1.4-9
- rebuild, revert from 1.2.0.1.
* Mon Feb 24 2003 Jeff Johnson <jbj@redhat.com> 1.1.4-8
- fix gzprintf buffer overrun (#84961).
* Wed Jan 22 2003 Tim Powers <timp@redhat.com> 1.1.4-7
- rebuilt
* Thu Nov 21 2002 Elliot Lee <sopwith@redhat.com> 1.1.4-6
- Make ./configure use $CC to ease cross-compilation
* Tue Nov 12 2002 Jeff Johnson <jbj@redhat.com> 1.1.4-5
- rebuild from cvs.
* Fri Jun 21 2002 Tim Powers <timp@redhat.com>
- automated rebuild
* Thu May 23 2002 Tim Powers <timp@redhat.com>
- automated rebuild
* Fri Apr 26 2002 Jakub Jelinek <jakub@redhat.com> 1.1.4-2
- remove glibc patch, it is no longer needed (zlib uses gcc -shared
  as it should)
- run tests and only build the package if they succeed
* Thu Apr 25 2002 Trond Eivind Glomsrød <teg@redhat.com> 1.1.4-1
- 1.1.4
* Wed Jan 30 2002 Trond Eivind Glomsrød <teg@redhat.com> 1.1.3-25.7
- Fix double free
* Sun Aug 26 2001 Trond Eivind Glomsrød <teg@redhat.com> 1.1.3-24
- Add example.c and minigzip.c to the doc files, as
  they are listed as examples in the README (#52574)
* Mon Jun 18 2001 Trond Eivind Glomsrød <teg@redhat.com>
- Updated URL
- Add version dependency for zlib-devel
- s/Copyright/License/
* Wed Feb 14 2001 Trond Eivind Glomsrød <teg@redhat.com>
- bumped version number - this is the old version without the performance enhancements
* Fri Sep 15 2000 Florian La Roche <Florian.LaRoche@redhat.de>
- add -fPIC for shared libs (patch by Fritz Elfert)
* Thu Sep  7 2000 Jeff Johnson <jbj@redhat.com>
- on 64bit systems, make sure libraries are located correctly.
* Thu Aug 17 2000 Jeff Johnson <jbj@redhat.com>
- summaries from specspo.
* Thu Jul 13 2000 Prospector <bugzilla@redhat.com>
- automatic rebuild
* Sun Jul  2 2000 Trond Eivind Glomsrød <teg@redhat.com>
- rebuild
* Tue Jun 13 2000 Jeff Johnson <jbj@redhat.com>
- FHS packaging to build on solaris2.5.1.
* Wed Jun  7 2000 Trond Eivind Glomsrød <teg@redhat.com>
- use %%%%{_mandir} and %%%%{_tmppath}
* Fri May 12 2000 Trond Eivind Glomsrød <teg@redhat.com>
- updated URL and source location
- moved README to main package
* Mon Feb  7 2000 Jeff Johnson <jbj@redhat.com>
- compress man page.
* Sun Mar 21 1999 Cristian Gafton <gafton@redhat.com> 
- auto rebuild in the new build environment (release 5)
* Wed Sep  9 1998 Cristian Gafton <gafton@redhat.com>
- link against glibc
* Mon Jul 27 1998 Jeff Johnson <jbj@redhat.com>
- upgrade to 1.1.3
* Fri May  8 1998 Prospector System <bugs@redhat.com>
- translations modified for de, fr, tr
* Wed Apr  8 1998 Cristian Gafton <gafton@redhat.com>
- upgraded to 1.1.2
- buildroot
* Tue Oct  7 1997 Donnie Barnes <djb@redhat.com>
- added URL tag (down at the moment so it may not be correct)
- made zlib-devel require zlib
* Thu Jun 19 1997 Erik Troan <ewt@redhat.com>
- built against glibc
