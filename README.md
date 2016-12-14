# regress_cc #
Regressing and isolating compiler behavior with respect to parameters.

Occasionally changing compiler directives generates buggy output. Since
simple options such as `-O2` imply dozens of options, manually regressing
which options cause the issue would be tedious and haphazard. Instead,
regress_cc automates discovering and testing implied option differences
using your pre-existing build system.

## Usage ##
In order to regress issues, the user must supply a predicate in the form
of a template that sets, compiles, and tests compiler options. So, for
make, this might be something like:

```
'CFLAGS="{}" make <some target> ; <execute target>'
```

For each automated test, brackets are replaced with compiler flags, and the
command is parsed and executed. Many commands can be joined with a semicolon
separator, which is useful for more complex build systems. For example, a
`meson.build` file could add an extra isolated parameters line `optimizers`:

```
project( 'MyProject', 'cpp' )
optimizers = [ '-O2' ]
flags = [ '-g', '-I./includes'] + optimizers
sources = [ ... ]
executable( 'MyTest', sources + [ 'MyTest.cpp' ], cpp_args : flags )
```
Which could be incorporated via a sed operation in the predicate:
```
'sed "s/optimizers = \[.*\]/optimizers = \[ {} \]/g" -i meson.build ; ninja -C build ; build/MyTest'
```
Of course, the format of the arguments needs to be modified for that to work, which
can be acheived via `--arg-format="'{}'"` to quote-escape each argument, and
`--arg-separator=', '` to comma-delimit the resultant list.

## Examples ##
Complete make example:
```
regress_cc.py --begin='-Og' --end='-O2' --predicate='CFLAGS="{}" make <some target> ; <execute target>'
```
Complete meson example:
```
regress_cc.py               \
  --begin='-Og -fno-inline' \
  --end='-Ofast -fno-gcse'  \
  --arg-format="'{}'"       \
  --arg-separator=', '      \
  --predicate='sed "s/optimizers = \[.*\]/optimizers = \[ {} \]/g" -i meson.build ; ninja -C build ; build/MyTest'
```
## TODOs ##
Improve regression:
  - Discover and account for argument dependencies.
  - Binary regression to speed up testing.
