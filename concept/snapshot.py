# This file is part of CO𝘕CEPT, the cosmological 𝘕-body code in Python.
# Copyright © 2015-2017 Jeppe Mosgaard Dakin.
#
# CO𝘕CEPT is free software: You can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CO𝘕CEPT is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CO𝘕CEPT. If not, see http://www.gnu.org/licenses/
#
# The author of CO𝘕CEPT can be contacted at dakin(at)phys.au.dk
# The latest version of CO𝘕CEPT is available at
# https://github.com/jmd-dk/concept/



# Import everything from the commons module.
# In the .pyx file, Cython declared variables will also get cimported.
from commons import *

# Cython imports
cimport('from communication import partition,                   '
        '                          domain_layout_local_indices, '
        '                          domain_subdivisions,         '
        '                          exchange,                    '
        '                          smart_mpi,                   '
        )
cimport('from mesh import slab_decompose')
cimport('from species import Component, FluidScalar, get_representation')

# Pure Python imports
import struct



# Class storing a standard snapshot. Besides holding methods for
# saving/loading, it stores component data.
@cython.cclass
class StandardSnapshot:
    """This class represents the standard snapshot type. Besides holding
    the components in the components list, the unit system is declared
    in the units dict. Finally, the cosmological parameters and the
    boxsize is stored in the params dict.
    """
    # The properly written name of this snapshot type
    # (only used for printing).
    name = 'standard'
    # The filename extension for this type of snapshot
    extension = '.hdf5'

    # Static method for identifying a file to be a snapshot of this type
    @staticmethod
    def is_this_type(filename):
        # Test for standard format by looking up the 'Ωcdm' attribute
        # in the HDF5 data structure.
        try:
            with h5py.File(filename, mode='r') as f:
                f.attrs[unicode('Ωcdm')]
                return True
        except:
            ...
        return False

    # Initialization method
    @cython.header
    def __init__(self):
        # The triple quoted string below serves as the type declaration
        # for the data attributes of the StandardSnapshot type.
        # It will get picked up by the pyxpp script
        # and indluded in the .pxd file.
        """
        public dict params
        public list components
        public dict units
        """
        # Dict containing all the parameters of the snapshot
        self.params = {}
        # List of components
        self.components = []
        # Dict containing the base units in str format
        self.units = {}

    # Methd that saves the snapshot to an hdf5 file
    @cython.pheader(# Argument
                   filename='str',
                   # Locals
                   component='Component',
                   domain_end_i='Py_ssize_t',
                   domain_end_j='Py_ssize_t',
                   domain_end_k='Py_ssize_t',
                   domain_size_i='Py_ssize_t',
                   domain_size_j='Py_ssize_t',
                   domain_size_k='Py_ssize_t',
                   domain_start_i='Py_ssize_t',
                   domain_start_j='Py_ssize_t',
                   domain_start_k='Py_ssize_t',
                   end_local='Py_ssize_t',
                   eos_message='str',
                   fluidscalar='FluidScalar',
                   indices='object',  # int or tuple
                   index='Py_ssize_t',
                   multi_index='tuple',
                   name='object',  # str or int
                   shape='tuple',
                   slab='double[:, :, ::1]',
                   slab_end='Py_ssize_t',
                   slab_start='Py_ssize_t',
                   start_local='Py_ssize_t',
                   ϱ_mv='double[:, :, ::1]',
                   returns='str',
                   )
    def save(self, filename):
        # Attach missing extension to filename
        if not filename.endswith('.hdf5'):
            filename += '.hdf5'
        # Print out message
        masterprint('Saving standard snapshot "{}" ...'.format(filename))
        with h5py.File(filename, mode='w', driver='mpio', comm=comm) as hdf5_file:
            # Save used base units
            hdf5_file.attrs['unit length']   = self.units['length']
            hdf5_file.attrs['unit time']     = self.units['time']
            hdf5_file.attrs['unit mass']     = self.units['mass']
            # Save global attributes
            hdf5_file.attrs['H0']            = self.params['H0']
            hdf5_file.attrs['a']             = self.params['a']
            hdf5_file.attrs['boxsize']       = self.params['boxsize']
            hdf5_file.attrs[unicode('Ωcdm')] = self.params['Ωcdm']
            hdf5_file.attrs[unicode('Ωb')]   = self.params['Ωb']
            # Store each component as a separate group
            # within /components.
            for component in self.components:
                component_h5 = hdf5_file.create_group('components/' + component.name)
                component_h5.attrs['species'] = component.species
                if component.representation == 'particles':
                    masterprint('Writing out {} ({} {}) ...'.format(component.name,
                                                                    component.N,
                                                                    component.species)
                                )
                    # Save particle attributes
                    component_h5.attrs['mass'] = component.mass
                    component_h5.attrs['N'] = component.N
                    # Get local indices of the particle data
                    start_local = int(np.sum(smart_mpi(component.N_local,
                                                       mpifun='allgather')[:rank]))
                    end_local = start_local + component.N_local
                    # Save particle data
                    shape = (component.N, )
                    posx_h5 = component_h5.create_dataset('posx', shape, dtype=C2np['double'])
                    posy_h5 = component_h5.create_dataset('posy', shape, dtype=C2np['double'])
                    posz_h5 = component_h5.create_dataset('posz', shape, dtype=C2np['double'])
                    momx_h5 = component_h5.create_dataset('momx', shape, dtype=C2np['double'])
                    momy_h5 = component_h5.create_dataset('momy', shape, dtype=C2np['double'])
                    momz_h5 = component_h5.create_dataset('momz', shape, dtype=C2np['double'])
                    posx_h5[start_local:end_local] = component.posx_mv[:component.N_local]
                    posy_h5[start_local:end_local] = component.posy_mv[:component.N_local]
                    posz_h5[start_local:end_local] = component.posz_mv[:component.N_local]
                    momx_h5[start_local:end_local] = component.momx_mv[:component.N_local]
                    momy_h5[start_local:end_local] = component.momy_mv[:component.N_local]
                    momz_h5[start_local:end_local] = component.momz_mv[:component.N_local]
                    # Done saving this particle component
                    masterprint('done')
                elif component.representation == 'fluid':
                    # Write out progress message
                    if component.w_type == 'constant':
                        eos_message = ('constant equation of state w = {}'
                                       .format(significant_figures(component.w_constant,
                                                                   6,
                                                                   fmt='unicode',
                                                                   incl_zeros=False,
                                                                   )
                                               )
                                       )
                    elif component.w_type == 'tabulated (t)':
                        eos_message = 'tabulated equation of state w(t)'
                    elif component.w_type == 'tabulated (a)':
                        eos_message = 'tabulated equation of state w(a)'
                    elif component.w_type == 'expression':
                        eos_message = 'equation of state w = {}'.format(component.w_expression)
                    else:
                        abort('Did not recognize w type "{}"'.format(component.w_type))
                    masterprint('Writing out {} ({} with '
                                'gridsize {}, '
                                '{} fluid variables, '
                                '{}) ...'
                                .format(component.name,
                                        component.species,
                                        component.gridsize,
                                        component.N_fluidvars,
                                        eos_message,
                                        ),
                                )
                    # Save fluid attributes
                    component_h5.attrs['gridsize'] = component.gridsize
                    component_h5.attrs['N_fluidvars'] = component.N_fluidvars
                    component_h5.attrs['w_type'] = component.w_type
                    if component.w_type == 'constant':
                        component_h5.attrs['w'] = component.w_constant
                    elif 'tabulated' in component.w_type:
                        # If w is tabulated it cannot be saved as
                        # an attribute. Instead save it as a dataset.
                        w_h5 = component_h5.create_dataset('w',
                                                           asarray(component.w_tabulated).shape,
                                                           dtype=C2np['double'])
                        if master:
                            w_h5[...] = component.w_tabulated
                    elif component.w_type == 'expression':
                        component_h5.attrs['w'] = component.w_expression
                    # Compute local indices of fluid grids
                    ϱ_mv = component.ϱ.grid_mv
                    domain_size_i = ϱ_mv.shape[0] - (1 + 2*2)
                    domain_size_j = ϱ_mv.shape[1] - (1 + 2*2)
                    domain_size_k = ϱ_mv.shape[2] - (1 + 2*2)
                    domain_start_i = domain_layout_local_indices[0]*domain_size_i
                    domain_start_j = domain_layout_local_indices[1]*domain_size_j
                    domain_start_k = domain_layout_local_indices[2]*domain_size_k
                    domain_end_i = domain_start_i + domain_size_i
                    domain_end_j = domain_start_j + domain_size_j
                    domain_end_k = domain_start_k + domain_size_k
                    # Save fluid grids in groups of name
                    # "fluidvar_index", with index = 0, 1, ...
                    # The fluid scalars are then datasets within
                    # these groups, named "fluidscalar_multi_index",
                    # with multi_index (0, ), (1, ), ..., (0, 0), ...
                    shape = (component.gridsize, )*3
                    for index, fluidvar in enumerate(component.fluidvars[:component.N_fluidvars]):
                        fluidvar_h5 = component_h5.create_group('fluidvar_{}'.format(index))
                        for multi_index in fluidvar.multi_indices:
                            fluidscalar = fluidvar[multi_index]
                            fluidscalar_h5 = fluidvar_h5.create_dataset('fluidscalar_{}'
                                                                        .format(multi_index),
                                                                        shape,
                                                                        dtype=C2np['double'])
                            # The global fluid scalar grid is of course
                            # stored contiguously on disk. Generally
                            # though, a single process does not store a
                            # contiguous part of this global grid,
                            # as it is domain decomposed rather than
                            # slab decomposed. Here we communicate the
                            # fluid scalar to slabs before saving to
                            # disk, improving performance enormously.
                            slab = slab_decompose(fluidscalar.grid_mv)
                            slab_start = slab.shape[0]*rank
                            slab_end = slab_start + slab.shape[0]
                            fluidscalar_h5[slab_start:slab_end, :, :] = slab[:,
                                                                             :,
                                                                             :component.gridsize]
                    # Create additional names (hard links) for the fluid
                    # groups and data sets. The names from
                    # component.fluid_names will be used, except for
                    # the additional linear variable, if CLASS is used
                    # to close the Boltzmann hierarchy
                    # (hence the try/except).
                    for name, indices in component.fluid_names.items():
                        if not isinstance(name, str) or name == 'ordered':
                            continue
                        if isinstance(indices, int):
                            # "name" is a fluid variable name (e.g. J,
                            # though not ϱ as this is a fluid scalar).
                            try:
                                fluidvar_h5 = component_h5['fluidvar_{}'.format(indices)]
                                component_h5[name] = fluidvar_h5
                            except:
                                ...
                        else:  # indices is a tuple
                            # "name" is a fluid scalar name (e.g. ϱ, Jx)
                            index, multi_index = indices
                            try:
                                fluidvar_h5 = component_h5['fluidvar_{}'.format(index)]
                                fluidscalar_h5 = fluidvar_h5['fluidscalar_{}'.format(multi_index)]  
                                component_h5[name] = fluidscalar_h5
                            except:
                                ...
                    # Done saving this fluid component
                    masterprint('done')
                elif master:
                    abort('Does not know how to save component "{}" with representation "{}"'
                          .format(component.name, component.representation))
        # Done saving the snapshot
        masterprint('done')
        # Return the filename of the saved file
        return filename

    # Method for loading in a standard snapshot from disk
    @cython.pheader(# Argument
                    filename='str',
                    only_params='bint',
                    # Locals
                    N='Py_ssize_t',
                    N_local='Py_ssize_t',
                    N_fluidvars='Py_ssize_t',
                    component='Component',
                    domain_end_i='Py_ssize_t',
                    domain_end_j='Py_ssize_t',
                    domain_end_k='Py_ssize_t',
                    domain_size_i='Py_ssize_t',
                    domain_size_j='Py_ssize_t',
                    domain_size_k='Py_ssize_t',
                    domain_start_i='Py_ssize_t',
                    domain_start_j='Py_ssize_t',
                    domain_start_k='Py_ssize_t',
                    end_local='Py_ssize_t',
                    eos_message='str',
                    fluidscalar='FluidScalar',
                    grid='double*',
                    gridsize='Py_ssize_t',
                    i='Py_ssize_t',
                    independent='str',
                    index='Py_ssize_t',
                    mass='double',
                    momx='double*',
                    momy='double*',
                    momz='double*',
                    multi_index='tuple',
                    name='str',
                    posx='double*',
                    posy='double*',
                    posz='double*',
                    representation='str',
                    shape='tuple',
                    size='Py_ssize_t',
                    snapshot_unit_length='double',
                    snapshot_unit_mass='double',
                    snapshot_unit_time='double',
                    species='str',
                    start_local='Py_ssize_t',
                    unit='double',
                    unit_J='double',
                    unit_σ='double',
                    unit_ϱ='double',
                    units_fluidvars='double[::1]',
                    w='object',  # float, str or np.ndarray
                    w_type='str',
                    )
    def load(self, filename, only_params=False):
        if only_params:
            masterprint('Loading parameters of snapshot "{}" ...'.format(filename))
        else:
            masterprint('Loading snapshot "{}" ...'.format(filename))
        # Load all components    
        with h5py.File(filename, mode='r', driver='mpio', comm=comm) as hdf5_file:
            # Load used base units
            self.units['length'] = hdf5_file.attrs['unit length']
            self.units['time']   = hdf5_file.attrs['unit time']
            self.units['mass']   = hdf5_file.attrs['unit mass']
            snapshot_unit_length = eval_unit(self.units['length'])
            snapshot_unit_time   = eval_unit(self.units['time'])
            snapshot_unit_mass   = eval_unit(self.units['mass'])
            # Load global attributes
            self.params['H0']      = hdf5_file.attrs['H0']*(1/snapshot_unit_time)
            self.params['a']       = hdf5_file.attrs['a']
            self.params['boxsize'] = hdf5_file.attrs['boxsize']*snapshot_unit_length
            self.params['Ωcdm']    = hdf5_file.attrs[unicode('Ωcdm')]
            self.params['Ωb']      = hdf5_file.attrs[unicode('Ωb')]
            # Load component data
            for name, component_h5 in hdf5_file['components'].items():
                species = component_h5.attrs['species']
                representation = get_representation(species)
                if representation == 'particles':
                    # Construct a Component instance and append it
                    # to this snapshot's list of components.
                    N = component_h5.attrs['N']
                    mass = component_h5.attrs['mass']*snapshot_unit_mass
                    component = Component(name, species, N, mass=mass)
                    self.components.append(component)
                    # Done loading component attributes
                    if only_params:
                        continue
                    masterprint('Reading in {} ({} {}) ...'.format(name, N, species))
                    # Extract HDF5 datasets
                    posx_h5 = component_h5['posx']
                    posy_h5 = component_h5['posy']
                    posz_h5 = component_h5['posz']
                    momx_h5 = component_h5['momx']
                    momy_h5 = component_h5['momy']
                    momz_h5 = component_h5['momz']
                    # Compute a fair distribution of 
                    # particle data to the processes.
                    start_local, N_local = partition(N)
                    end_local = start_local + N_local
                    # Populate the Component instance with data from the file
                    component.populate(posx_h5[start_local:end_local], 'posx')
                    component.populate(posy_h5[start_local:end_local], 'posy')
                    component.populate(posz_h5[start_local:end_local], 'posz')
                    component.populate(momx_h5[start_local:end_local], 'momx')
                    component.populate(momy_h5[start_local:end_local], 'momy')
                    component.populate(momz_h5[start_local:end_local], 'momz')
                    posx = component.posx
                    posy = component.posy
                    posz = component.posz
                    momx = component.momx
                    momy = component.momy
                    momz = component.momz
                    # If the snapshot and the current run uses different
                    # systems of units, mulitply the component positions
                    # and momenta by the snapshot units.
                    if snapshot_unit_length != 1:
                        for i in range(N_local):
                            posx[i] *= snapshot_unit_length
                            posy[i] *= snapshot_unit_length
                            posz[i] *= snapshot_unit_length
                    unit = snapshot_unit_length/snapshot_unit_time*snapshot_unit_mass
                    if unit != 1:
                        for i in range(N_local):
                            momx[i] *= unit
                            momy[i] *= unit
                            momz[i] *= unit
                    # Done reading in particle component
                    masterprint('done')
                elif representation == 'fluid':
                    # Read in fluid attributes
                    gridsize = component_h5.attrs['gridsize']
                    N_fluidvars = component_h5.attrs['N_fluidvars']
                    w_type = component_h5.attrs['w_type']
                    if 'tabulated' in w_type:
                        # The equation of state parameter w is saved
                        # as a dataset.
                        w = component_h5['w']
                        # Transform w to a dict of the format
                        # {'t': t, 'w': w} or {'a': a, 'w': w}.
                        independent = re.search('\((.+)\)', w_type).group(1)
                        w = {independent: w[0, :], 'w': w[1, :]}
                    else:
                        w = component_h5.attrs['w']
                    # Construct a Component instance and append it
                    # to this snapshot's list of components.
                    component = Component(name, species, gridsize,
                                          N_fluidvars=N_fluidvars, w=w)
                    self.components.append(component)
                    # Done loading component attributes
                    if only_params:
                        continue
                    # Write out progress message
                    if w_type == 'constant':
                        eos_message = ('constant equation of state w = {}'
                                       .format(significant_figures(w,
                                                                   6,
                                                                   fmt='unicode',
                                                                   incl_zeros=False,
                                                                   )
                                               )
                                       )
                    elif w_type == 'tabulated (t)':
                        eos_message = 'tabulated equation of state w(t)'
                    elif w_type == 'tabulated (a)':
                        eos_message = 'tabulated equation of state w(a)'
                    elif w_type == 'expression':
                        eos_message = 'equation of state w = {}'.format(w)
                    masterprint('Reading in {} ({} with '
                                'gridsize {}, '
                                '{} fluid variables, '
                                '{}) ...'
                                .format(name,
                                        species,
                                        gridsize,
                                        N_fluidvars,
                                        eos_message,
                                        )
                                )
                    # Compute local indices of fluid grids
                    domain_size_i = gridsize//domain_subdivisions[0]
                    domain_size_j = gridsize//domain_subdivisions[1]
                    domain_size_k = gridsize//domain_subdivisions[2]
                    if master and (   gridsize != domain_subdivisions[0]*domain_size_i
                                   or gridsize != domain_subdivisions[1]*domain_size_j
                                   or gridsize != domain_subdivisions[2]*domain_size_k):
                        abort('The gridsize of the {} component is {} '
                              'which cannot be equally shared among {} processes'
                              .format(name, gridsize, nprocs))
                    domain_start_i = domain_layout_local_indices[0]*domain_size_i
                    domain_start_j = domain_layout_local_indices[1]*domain_size_j
                    domain_start_k = domain_layout_local_indices[2]*domain_size_k
                    domain_end_i = domain_start_i + domain_size_i
                    domain_end_j = domain_start_j + domain_size_j
                    domain_end_k = domain_start_k + domain_size_k
                    # Fluid scalars are already instantiated.
                    # Now populate them.
                    for index, fluidvar in enumerate(component.fluidvars[:component.N_fluidvars]):
                        fluidvar_h5 = component_h5['fluidvar_{}'.format(index)]
                        for multi_index in fluidvar.multi_indices:
                            fluidscalar_h5 = fluidvar_h5['fluidscalar_{}'.format(multi_index)]
                            # Note that this also performs the needed
                            # communication to populate pseudo and
                            # ghost points.
                            component.populate(fluidscalar_h5[domain_start_i:domain_end_i,
                                                              domain_start_j:domain_end_j,
                                                              domain_start_k:domain_end_k],
                                               index, multi_index)
                    # If the snapshot and the current run uses different
                    # systems of units, mulitply the fluid data
                    # by the snapshot units.
                    unit_ϱ = snapshot_unit_mass/snapshot_unit_length**3
                    unit_J = snapshot_unit_mass/(snapshot_unit_length**2*snapshot_unit_time)
                    unit_σ = 1
                    units_fluidvars = asarray((unit_ϱ, unit_J, unit_σ), dtype=C2np['double'])
                    size = np.prod(component.shape)
                    for fluidvar, unit in zip(component.fluidvars[:component.N_fluidvars],
                                              units_fluidvars):
                        if unit == 1:
                            continue
                        for fluidscalar in fluidvar:
                            grid = fluidscalar.grid
                            for i in range(size):
                                grid[i] *= unit
                    # Done reading in fluid component
                    masterprint('done')
                elif master:
                    abort('Does not know how to load component "{}" with representation "{}"'
                          .format(name, representation))
        # Done loading the snapshot
        masterprint('done')

    # This method populate the snapshot with component data
    # and additional parameters.
    @cython.pheader(# Arguments
                    components='list',
                    params='dict',
                    # Locals
                    key='str',
                    )
    def populate(self, components, params={}):
        # Pupulate snapshot with the components
        self.components = components
        # Populate snapshot with the passed scalefactor
        # and global parameters. If a params dict is passed,
        # use values from this instead.
        self.params['H0']      = params.get('H0',      H0)
        if enable_Hubble:
            self.params['a']   = params.get('a',       universals.a)
        else:
            self.params['a']   = universals.a
        self.params['boxsize'] = params.get('boxsize', boxsize)
        self.params['Ωcdm']    = params.get('Ωcdm'   , Ωcdm)
        self.params['Ωb']      = params.get('Ωb'     , Ωb)
        # Populate the base units with the global base units
        self.units['length'] = unit_length
        self.units['time']   = unit_time
        self.units['mass']   = unit_mass

# Class storing a Gadget2 snapshot. Besides holding methods for
# saving/loading, it stores particle data (positions, momenta, mass)
# and also Gadget ID's and the Gadget header.
@cython.cclass
class Gadget2Snapshot:
    """This class represents snapshots of the "gadget2" type, meaning
    the second type of snapshot native to GADGET2. Only GADGET2 type 1
    (halo) particles, corresponding to dark matter particles, are
    supported. It is however also possible to save a component with a
    species of "matter" as a Gadget2Snapshot.
    As is the case for the standard snapshot class, this class contains
    a list components (the components attribute) and dict of parameters
    (the params attribute). Besides holding the cosmological parameters
    and the boxsize, the params dict also contains a a "header" key,
    the item of which is the GADGET2 header, represented as an ordered
    dict. This class does not have a units attribute, as no global
    unit system is used by GADGET snapshots.
    As only a single component (GADGET halos) are supported, the
    components list will always contain this single component only. For
    ease of access, the component attribute is also defined, referring
    directly to this component. Finally, the ID attribute holds the
    GADGET IDs of particles. When constructing a Gadget2Snapshot
    instance by other means than by loading from a snapshot on disk,
    these are generated in a somewhat arbitrary (but consistent)
    fashion.
    """
    # The properly written name of this snapshot type
    # (only used for printing).
    name = 'GADGET2'
    # The filename extension for this type of snapshot
    extension = ''

    # Static method for identifying a file to be a snapshot of this type
    @staticmethod
    def is_this_type(filename):
        # Test for GADGET2 format by checking the existence
        # of the 'HEAD' identifier.
        try:
            with open(filename, 'rb') as f:
                f.seek(4)
                head = struct.unpack('4s', f.read(struct.calcsize('4s')))
                if head[0] == b'HEAD':
                    return True
        except:
            ...
        return False

    # Initialization method
    @cython.header
    def __init__(self):
        # The triple quoted string below serves as the type declaration
        # for the data attributes of the Gadget2Snapshot type.
        # It will get picked up by the pyxpp script
        # and indluded in the .pxd file.
        """
        public dict params
        public list components
        Component component
        unsigned int[::1] ID
        """
        # Dict containing all the parameters of the snapshot
        self.params = {}
        # List of Component instances (will only ever hold
        # self.component, which can only be GADGET halos).
        self.components = []
        # The actual component data
        self.component = None
        # The ID of each particle (not used by the CO𝘕CEPT code)
        self.ID = None

    # Method for saving a GADGET2 snapshot of type 2 to disk
    @cython.pheader(# Arguments
                    filename='str',
                    # Locals
                    N='Py_ssize_t',
                    N_local='Py_ssize_t',
                    i='int',
                    component='Component',
                    unit='double',
                    returns='str',
                    )
    def save(self, filename):
        """The snapshot data (positions and velocities) are stored in
        single precision. Only GADGET2 type 1 (halo) particles,
        corresponding to dark matter (or matter) particles,
        are supported.
        """
        masterprint('Saving GADGET2 snapshot "{}" ...'.format(filename))
        component = self.component
        if master and component.species not in ('dark matter particles', 'matter particles'):
            abort('The GAGDET2 snapshot type can only store dark matter or matter particles '
                  '(the species of the {} component is "{}")'
                  .format(component.name, component.species))
        N = component.N
        N_local = component.N_local
        header = self.params['header']
        # The master process write the HEAD block
        if master:
            with open(filename, 'wb') as f:
                # 8 = 4*1 + 4 = 4*sizeof(s) + sizeof(i)
                f.write(struct.pack('I', 8))
                f.write(struct.pack('4s', b'HEAD'))
                # sizeof(i) + 256 + sizeof(i)
                f.write(struct.pack('I', 4 + 256 + 4))
                f.write(struct.pack('I', 8))
                f.write(struct.pack('I', 256))
                f.write(struct.pack('6I', *header['Npart']))
                f.write(struct.pack('6d', *header['Massarr']))
                f.write(struct.pack('d',   header['Time']))
                f.write(struct.pack('d',   header['Redshift']))
                f.write(struct.pack('i',   header['FlagSfr']))
                f.write(struct.pack('i',   header['FlagFeedback']))
                f.write(struct.pack('6i', *header['Nall']))
                f.write(struct.pack('i',   header['FlagCooling']))
                f.write(struct.pack('i',   header['Numfiles']))
                f.write(struct.pack('d',   header['BoxSize']))
                f.write(struct.pack('d',   header['Omega0']))
                f.write(struct.pack('d',   header['OmegaLambda']))
                f.write(struct.pack('d',   header['HubbleParam']))
                f.write(struct.pack('i',   header['FlagAge']))
                f.write(struct.pack('i',   header['FlagMetals']))
                f.write(struct.pack('6i', *header['NallHW']))
                f.write(struct.pack('i',   header['flag_entr_ics']))
                # Padding to fill out the 256 bytes
                f.write(struct.pack('60s', b' '*60))
                f.write(struct.pack('I', 256))
        masterprint('Writing out {} ({} {}) ...'.format(component.name,
                                                        component.N,
                                                        component.species)
                    )
        # Write the POS block in serial, one process at a time
        unit = units.kpc/header['HubbleParam']
        for i in range(nprocs):
            Barrier()
            if i == rank:
                with open(filename, 'ab') as f:
                    # The identifier
                    if i == 0:
                        # 8 = 4*1 + 4 = 4*sizeof(s) + sizeof(i)
                        f.write(struct.pack('I', 8))
                        f.write(struct.pack('4s', b'POS '))
                        # sizeof(i) + 3*N*sizeof(f) + sizeof(i)
                        f.write(struct.pack('I', 4 + 3*N*4 + 4))
                        f.write(struct.pack('I', 8))
                        f.write(struct.pack('I', 3*N*4))
                    # The data
                    (asarray(np.vstack((component.posx_mv[:N_local],
                                        component.posy_mv[:N_local],
                                        component.posz_mv[:N_local])
                                       ).T.flatten(),
                             dtype=C2np['float'])/unit).tofile(f)
                    # The closing int
                    if i == nprocs - 1:
                        f.write(struct.pack('I', 3*N*4))
        # Write the VEL block in serial, one process at a time
        unit = units.km/units.s*component.mass*header['Time']**1.5
        for i in range(nprocs):
            Barrier()
            if i == rank:
                with open(filename, 'ab') as f:
                    # The identifier
                    if i == 0:
                        # 8 = 4*1 + 4 = 4*sizeof(s) + sizeof(i)
                        f.write(struct.pack('I', 8))
                        f.write(struct.pack('4s', b'VEL '))
                        # sizeof(i) + 3*N*sizeof(f) + sizeof(i)
                        f.write(struct.pack('I', 4 + 3*N*4 + 4))
                        f.write(struct.pack('I', 8))
                        f.write(struct.pack('I', 3*N*4))
                    # The data
                    (asarray(np.vstack((component.momx_mv[:N_local],
                                        component.momy_mv[:N_local],
                                        component.momz_mv[:N_local])
                                       ).T.flatten(),
                             dtype=C2np['float'])/unit).tofile(f)
                    # The closing int
                    if i == nprocs - 1:
                        f.write(struct.pack('i', 3*N*4))
        # Write the ID block in serial, one process at a time
        for i in range(nprocs):
            Barrier()
            if i == rank:
                with open(filename, 'ab') as f:
                    # The identifier
                    if i == 0:
                        # 8 = 4*1 + 4 = 4*sizeof(s) + sizeof(i)
                        f.write(struct.pack('I', 8))
                        f.write(struct.pack('4s', b'ID  '))
                        # sizeof(i) + N*sizeof(I) + sizeof(i)
                        f.write(struct.pack('I', 4 + N*4 + 4))
                        f.write(struct.pack('I', 8))
                        f.write(struct.pack('I', N*4))
                    # The data
                    asarray(self.ID, dtype=C2np['unsigned int']).tofile(f)
                    # The closing int
                    if i == nprocs - 1:
                        f.write(struct.pack('I', N*4))
        # Finalize progress messages
        masterprint('done')
        masterprint('done')
        # Return the filename of the saved file
        return filename

    # Method for loading in a GADGET2 snapshot of type 2 from disk
    @cython.pheader(# Arguments
                    filename='str',
                    only_params='bint',
                    # Locals
                    N='Py_ssize_t',
                    N_local='Py_ssize_t',
                    blockname='str',
                    file_position='Py_ssize_t',
                    header='object',  # collections.OrderedDict
                    mass='double',
                    name='str',
                    offset='Py_ssize_t',
                    size='unsigned int',
                    species='str',
                    start_local='Py_ssize_t',
                    unit='double',
                    )
    def load(self, filename, only_params=False):
        """ It is assumed that the snapshot on the disk is a GADGET2
        snapshot of type 2 and that it uses single precision. The
        Gadget2Snapshot instance stores the data (positions and
        velocities) in double precision. Only GADGET type 1 (halo)
        particles, corresponding to dark matter particles,
        are supported.
        """
        if only_params:
            masterprint('Loading parameters of snapshot "{}" ...'.format(filename))
        else:
            masterprint('Loading snapshot "{}" ...'.format(filename))
        # Only type 1 (halo) particles are supported
        name = 'GADGET halos'
        species = 'dark matter particles'
        # Read in the snapshot
        offset = 0
        with open(filename, 'rb') as f:
            # Read the HEAD block into a params['header'] dict.
            # No unit conversion will be done.
            offset = self.new_block(f, offset)
            blockname = self.read(f, '4s').decode('utf8')  # "HEAD"
            size = self.read(f, 'I')  # 264
            offset = self.new_block(f, offset)
            self.params['header'] = collections.OrderedDict()
            header = self.params['header']
            header['Npart']         = self.read(f, '6I')
            header['Massarr']       = self.read(f, '6d')
            header['Time']          = self.read(f, 'd')
            header['Redshift']      = self.read(f, 'd')
            header['FlagSfr']       = self.read(f, 'i')
            header['FlagFeedback']  = self.read(f, 'i')
            header['Nall']          = self.read(f, '6i')
            header['FlagCooling']   = self.read(f, 'i')
            header['NumFiles']      = self.read(f, 'i')
            header['BoxSize']       = self.read(f, 'd')
            header['Omega0']        = self.read(f, 'd')
            header['OmegaLambda']   = self.read(f, 'd')
            header['HubbleParam']   = self.read(f, 'd')
            header['FlagAge']       = self.read(f, 'i')
            header['FlagMetals']    = self.read(f, 'i')
            header['NallHW']        = self.read(f, '6i')
            header['flag_entr_ics'] = self.read(f, 'i')
            # Also include some of the header fields as parameters
            # directly in the params dict. These are the same as
            # those included in the params dict of
            # standard type snapshots.
            unit = 100*units.km/(units.s*units.Mpc)
            self.params['H0']      = header['HubbleParam']*unit
            self.params['a']       = header['Time']
            unit = units.kpc/header['HubbleParam']
            self.params['boxsize'] = header['BoxSize']*unit
            self.params['Ωm']      = header['Omega0']
            self.params['ΩΛ']      = header['OmegaLambda']
            # Construct a Component instance and pack it
            # into this snapshot's list of components.
            N = header['Npart'][1]
            unit = 1e+10*units.m_sun/header['HubbleParam']
            mass = header['Massarr'][1]*unit
            self.component = Component(name, species, N, mass=mass)
            self.components = [self.component]
            # Done loading component attributes
            if only_params:
                masterprint('done')
                return
            masterprint('Reading in {} ({} {}) ...'.format(name, N, species))
            # Compute a fair distribution
            # of component data to the processes.
            start_local, N_local = partition(N)
            # Read in the POS block. The positions are given in kpc/h.
            offset = self.new_block(f, offset)
            unit = units.kpc/header['HubbleParam']
            blockname = self.read(f, '4s').decode('utf8')  # "POS "
            size = self.read(f, 'I')
            offset = self.new_block(f, offset)
            f.seek(12*start_local, 1)  # 12 = sizeof(float)*3
            file_position = f.tell()
            self.component.populate(asarray(np.fromfile(f, dtype=C2np['float'], count=3*N_local)
                                            [0::3], dtype=C2np['double'])*unit,
                                    'posx')
            f.seek(file_position)
            self.component.populate(asarray(np.fromfile(f, dtype=C2np['float'], count=3*N_local)
                                            [1::3], dtype=C2np['double'])*unit,
                                    'posy')
            f.seek(file_position)
            self.component.populate(asarray(np.fromfile(f, dtype=C2np['float'], count=3*N_local)
                                            [2::3], dtype=C2np['double'])*unit,
                                    'posz')
            # Read in the VEL block. The velocities are peculiar
            # velocities u=a*dx/dt divided by sqrt(a), given in km/s.
            offset = self.new_block(f, offset)
            unit = units.km/units.s*mass*header['Time']**1.5
            blockname = self.read(f, '4s').decode('utf8')  # "VEL "
            size = self.read(f, 'I')
            offset = self.new_block(f, offset)
            f.seek(12*start_local, 1)  # 12 = sizeof(float)*3
            file_position = f.tell()
            self.component.populate(asarray(np.fromfile(f, dtype=C2np['float'], count=3*N_local)
                                            [0::3], dtype=C2np['double'])*unit,
                                    'momx')
            f.seek(file_position)
            self.component.populate(asarray(np.fromfile(f, dtype=C2np['float'], count=3*N_local)
                                            [1::3], dtype=C2np['double'])*unit,
                                    'momy')
            f.seek(file_position)
            self.component.populate(asarray(np.fromfile(f, dtype=C2np['float'], count=3*N_local)
                                            [2::3], dtype=C2np['double'])*unit,
                                    'momz')
            # Read in the ID block.
            # The ID's will be distributed among all processes.
            offset = self.new_block(f, offset)
            blockname = self.read(f, '4s').decode('utf8')  # "ID  "
            size = self.read(f, 'I')
            offset = self.new_block(f, offset)
            f.seek(4*start_local, 1)  # 4 = sizeof(unsigned int)
            file_position = f.tell()
            self.ID = np.fromfile(f, dtype=C2np['unsigned int'], count=N_local)
            # Done reading in particles
            masterprint('done')
            # Possible additional meta data ignored
        # Done loading the snapshot
        masterprint('done')

    # This method populate the snapshot with component data
    # as well as ID's (which are not used by this code) and
    # additional header information.
    @cython.pheader(# Arguments
                    components='list',
                    params='dict',
                    # Locals
                    component='Component',
                    start_local='Py_ssize_t',
                    ΩΛ='double',
                    )
    def populate(self, components, params={}):
        """The following header fields depend on the particles:
            Npart, Massarr, Nall.
        The following header fields depend on the current time:
            Time, Redshift.
        The following header fields correspond to the parameters
        used in the current run:
            BoxSize, Omega0, OmegaLambda, HubbleParam.
        All other fields get generic values.
        """
        # Pupulate snapshot with the GADGTE halos
        component = components[0]
        self.component = component
        self.components = [component]
        # The ID's of the local particles, generated such that
        # the process with the lowest rank has the lowest ID's.
        start_local = int(np.sum(smart_mpi(component.N_local, mpifun='allgather')[:rank]))
        self.ID = arange(start_local, start_local + component.N_local, dtype=C2np['unsigned int'])
        # Populate snapshot with the passed scalefactor
        # and global parameters. If a params dict is passed,
        # use values from this instead.
        self.params['H0']      = params.get('H0',      H0)
        if enable_Hubble:
            self.params['a']   = params.get('a',       universals.a)
        else:
            self.params['a']   = universals.a
        self.params['boxsize'] = params.get('boxsize', boxsize)
        self.params['Ωm']      = params.get('Ωm',      Ωm)
        ΩΛ = 1 - self.params['Ωm']  # Flat universe with only matter and cosmological constant
        self.params['ΩΛ']      = params.get('ΩΛ',      ΩΛ)
        # Build the GADGET header
        self.update_header()

    # Method for constructing the GADGET header from the other
    # parameters in the params dict.
    @cython.header(# Locals
                   component='Component',
                   h='double',
                   header='object',  # collections.OrderedDict
                   params='dict',
                   unit='double',
                   )
    def update_header(self):
        # Extract variabled
        component = self.component
        params = self.params
        # The GADGET header is constructed from scratch
        params['header'] = collections.OrderedDict()
        header = params['header']
        # Fill the header
        header['Npart'] = [0, component.N, 0, 0, 0, 0]
        unit = 100*units.km/(units.s*units.Mpc)
        h = params['H0']/unit
        unit = 1e+10*units.m_sun/h
        header['Massarr']       = [0.0, component.mass/unit, 0.0, 0.0, 0.0, 0.0]
        header['Time']          = params['a']
        header['Redshift']      = 1/params['a'] - 1
        header['FlagSfr']       = 0
        header['FlagFeedback']  = 0
        header['Nall']          = [0, component.N, 0, 0, 0, 0]
        header['FlagCooling']   = 0
        header['Numfiles']      = 1
        unit = units.kpc/h
        header['BoxSize']       = params['boxsize']/unit
        header['Omega0']        = params['Ωm']
        header['OmegaLambda']   = params['ΩΛ']
        header['HubbleParam']   = h
        header['FlagAge']       = 0
        header['FlagMetals']    = 0
        header['NallHW']        = [0, 0, 0, 0, 0, 0]
        header['flag_entr_ics'] = 1

    # Method used for reading series of bytes from the snapshot file
    @cython.header(# Arguments
                   f='object',
                   fmt='str',
                   # Locals
                   t='tuple',
                   returns='object',
                   )
    def read(self, f, fmt):
        # Convert bytes to python objects and store them in a tuple
        t = struct.unpack(fmt, f.read(struct.calcsize(fmt)))
        # If the tuple contains just a single element, return this
        # element rather than the tuple.
        if len(t) == 1:
            return t[0]
        # It is nicer to use mutable lists than immutable tuples
        return list(t)

    # Method that handles the file object's position in the snapshot
    # file during loading. Call it when the next block should be read.
    @cython.header(offset='Py_ssize_t',
                   f='object',
                   returns='Py_ssize_t',
                   )
    def new_block(self, f, offset):
        # Set the current position in the file
        f.seek(offset)
        # Each block is bracketed with a 4-byte int
        # containing the size of the block
        offset += 8 + self.read(f, 'I')
        return offset

# Function that saves the current state of the simulation
# - consisting of global parameters as well as the list of components -
# to a snapshot file. The type of snapshot to be saved is determined by
# the snapshot_type parameter.
@cython.pheader(# Argument
                one_or_more_components='object',  # Component or container of Components
                filename='str',
                params='dict',
                # Locals
                snapshot='object',  # Any implemented snapshot type
                returns='str',
                )
def save(one_or_more_components, filename, params={}):
    """Note that since we want this function to be exposed to
    pure Python, a pheader is used.
    """
    # Instantiate snapshot of the appropriate type
    snapshot = eval(snapshot_type.capitalize() + 'Snapshot()')
    # Populate the snapshot with data
    if isinstance(one_or_more_components, Component):
        components = [one_or_more_components]
    else:
        components = list(one_or_more_components)
    snapshot.populate(components, params)
    # Make sure that the directory of the snapshot exists
    if master:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
    Barrier()
    # Save the snapshot to disk.
    # The (maybe altered) filename is returned,
    # which should also be the return value of this function.
    return snapshot.save(filename)

# Function that loads a snapshot file.
# The type of snapshot can be any of the implemented.
@cython.pheader(# Argument
                filename='str',
                compare_params='bint',
                only_params='bint',
                only_components='bint',
                do_exchange='bint',
                as_if='str',
                # Locals
                component='Component',
                i='Py_ssize_t',
                input_type='str',
                snapshot='object',          # Some snapshot type
                snapshot_newtype='object',  # Some snapshot type
                returns='object',           # Snapshot or list
                )
def load(filename, compare_params=True,
                   only_params=False,
                   only_components=False,
                   do_exchange=True,
                   as_if=''):
    """When only_params == False and only_components == False,
    the return type is simply a snapshot object containing all the
    data in the snapshot on disk.
    When only_components == True, a list of components within
    the snapshot will be returned.
    When only_params == True, a snapshot object will be returned,
    containing both parameters (.params) and components (.components),
    just as when only_params == False. These components will have
    correctly specified attributes, but no actual component data.
    """
    # If no snapshot should be loaded, return immediately
    if not filename:
        return
    # Determine snapshot type
    input_type = get_snapshot_type(filename)
    if master and input_type is None:
        abort('Cannot recognize "{}" as one of the implemented snapshot types ({}).'
              .format(filename,
                      ', '.join([snapshot_class.name for snapshot_class in snapshot_classes])))
    # Instantiate snapshot of the appropriate type
    snapshot = eval(input_type.capitalize() + 'Snapshot()')
    # Load the snapshot from disk
    snapshot.load(filename, only_params=only_params)
    # Check if the parameters of the snapshot matches those of the
    # current simulation run. Display a warning if they do not.
    if compare_params:
        compare_parameters(snapshot.params, filename)
    # Check that all particles are positioned within the box.
    # Particles exactly on the upper boundaries will be moved to the
    # physically equivalent lower boundaries.
    for component in snapshot.components:
        out_of_bounds_check(component, snapshot.params['boxsize'])
    # Scatter particles to the correct domain-specific process.
    # Also communicate pseudo and ghost points of fluid variables.
    if not only_params and do_exchange:
        # Do exchanges for all components. Reset the communication
        # buffers after the last exchange, as these initial exchanges
        # are not representable for those to come during the
        # actual simulation.
        for i, component in enumerate(snapshot.components):
            exchange(component, reset_buffers=(i == len(snapshot.components) - 1))
        # Communicate the pseudo and ghost points
        # of all fluid variables in fluid components.
        for component in snapshot.components:
            component.communicate_fluid_grids(mode='populate')
    # If the caller is interested in the components only,
    # return the list of components.
    if only_components:
        return snapshot.components
    # If a specific snapshot type is required, build this snapshot
    # and populate it with the loaded data.
    if as_if and as_if != input_type:
        snapshot_newtype = eval(as_if.capitalize() + 'Snapshot()')
        snapshot_newtype.populate(snapshot.components, snapshot.params)
        return snapshot_newtype
    # Return the loaded snapshot
    return snapshot

# Function for determining the snapshot type of a file
@cython.header(# Arguments
               filename='str',
               # Locals
               head='tuple',
               returns='str',
               )
def get_snapshot_type(filename):
    """Call the 'is_this_type' class method of each snapshot class until
    the file is recognized as a specific snapshot type.
    The returned name of the snapshot type is in the same format as the
    explicit name of the snapshot class, but with the "Snapshot" suffix
    removed and all characters are converted to lowercase.
    If the file is not recognized as any snapshot type at all,
    do not throw an error but simply return None.
    """
    # Abort if the file does not exist
    if master and not os.path.exists(filename):
        abort('The snapshot file "{}" does not exist'.format(filename))
    # Get the snapshot type by asking each snapshot class whether they
    # recognize the file.
    for snapshot_class in snapshot_classes:
        if snapshot_class.is_this_type(filename):
            return snapshot_class.__name__.rstrip('Snapshot').lower()
    # Return None if the file is not a valid snapshot
    return None

# Function whick takes in a dict of parameters and compare their
# values to those of the current run. If any disagreement is found,
# write a warning message.
@cython.header(# Arguments
               params='dict',
               filename='str',
               # Locals
               indent_str='str',
               msg='str',
               rel_tol='double',
               unit='double',
               vs='str',
               )
def compare_parameters(params, filename):
    """Specifically, the following parameters are compared:
    a (compared against a_begin)
    boxsize
    H0
    Ωcdm
    Ωb
    """
    # The relative tolerence by which the parameters are compared
    rel_tol = 1e-6
    # Format strings
    vs = '{{:.{num}g}} vs {{:.{num}g}}'.format(num=int(1 - log10(rel_tol)))
    indent_str = '\n    '
    msg = ''
    # Do the comparisons one by one
    if enable_Hubble and not isclose(a_begin, float(params['a']), rel_tol):
        msg += '{}a_begin: {}'.format(indent_str,
                                      vs.format(a_begin, params['a']))
    if not isclose(boxsize, float(params['boxsize']), rel_tol):
        msg += '{}boxsize: {} [{}]'.format(indent_str,
                                           vs.format(boxsize, params['boxsize']),
                                           unit_length)
    if not isclose(H0, float(params['H0']), rel_tol):
        unit = units.km/(units.s*units.Mpc)
        msg += '{}H0: {} [km s⁻¹ Mpc⁻¹]'.format(indent_str,
                                                vs.format(H0/unit, params['H0']/unit))
    if 'Ωb' in params:
        if not isclose(Ωb, float(params['Ωb']), rel_tol):
            msg += '{}Ωb: {}'.format(indent_str,
                                     vs.format(Ωm, params['Ωb']))
    if 'Ωcdm' in params:
        if not isclose(Ωcdm, float(params['Ωcdm']), rel_tol):
            msg += '{}Ωcdm: {}'.format(indent_str,
                                       vs.format(Ωm, params['Ωcdm']))
    if 'Ωm' in params:
        if not isclose(Ωm, float(params['Ωm']), rel_tol):
            msg += '{}Ωm: {}'.format(indent_str,
                                     vs.format(Ωm, params['Ωm']))
    if msg:
        msg = ('Mismatch between current parameters and those in the snapshot "{}":{}'
               ).format(filename, msg)
        masterwarn(msg, skipline=False)

# Function which does a sanity check of particle components,
# ensuring that they are within the box.
@cython.header(# Arguments
               component='Component',
               snapshot_boxsize='double',
               # Locals
               i='Py_ssize_t',
               posx='double*',
               posy='double*',
               posz='double*',
               )
def out_of_bounds_check(component, snapshot_boxsize=-1):
    """If any particles are outside of the box, the program
    will terminate. Particles located exactly at the upper box
    boundaries will be moved to the (physically equivalent) lower
    boundaries. Note that no communication will be performed! Therefore,
    you should always call the exchange function after this function.
    """
    # Only components with particle representation can be out of bounds,
    # as these are the only ones with explicit positions.
    if component.representation != 'particles':
        return
    # If no boxsize is passed, use the global boxsize
    if snapshot_boxsize == -1:
        snapshot_boxsize = boxsize
    # Extract position variables
    posx = component.posx
    posy = component.posy
    posz = component.posz
    # Do the check for each particle in the component
    for i in range(component.N_local):
        # Move particles at the very upper boundaries of the box
        # to the lower boundaries instead.
        if posx[i] == snapshot_boxsize:
            posx[i] = 0
        if posy[i] == snapshot_boxsize:
            posy[i] = 0
        if posz[i] == snapshot_boxsize:
            posz[i] = 0
        # Abort on out of bounds
        if (   not (0 <= posx[i] < snapshot_boxsize)
            or not (0 <= posy[i] < snapshot_boxsize)
            or not (0 <= posz[i] < snapshot_boxsize)):
            abort('Particle number {} of component "{}" has position '
                  '({:.9g}, {:.9g}, {:.9g}) {}, which is outside of the cubic box '
                  'of side length {:.9g} {}'.format(i,
                                                    component.name, 
                                                    posx[i],
                                                    posy[i],
                                                    posz[i],
                                                    unit_length,
                                                    snapshot_boxsize,
                                                    unit_length),
                  )



# Construct tuple of possible filename extensions for snapshots
# by simply grabbing the 'extension' class variable off of all
# classes defined in this module with the name '...Snapshot'.
cython.declare(snapshot_classes='tuple',
               snapshot_extensions='tuple',
               )
snapshot_classes = tuple([var for name, var in globals().items()
                          if (    hasattr(var, '__module__')
                              and var.__module__ == 'snapshot'
                              and inspect.isclass(var)
                              and name.endswith('Snapshot')
                              )
                          ])
snapshot_extensions = tuple(set([snapshot_class.extension for snapshot_class in snapshot_classes
                                 if snapshot_class.extension]))
