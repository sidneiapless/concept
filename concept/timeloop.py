# Import everything from the commons module. In the .pyx file,
# this line will be replaced by the content of commons.py itself.
from commons import *

# Seperate but equivalent imports in pure Python and Cython
if not cython.compiled:
    from species import construct, construct_random
    from IO import save, load
    from integration import expand, cosmic_time, scalefactor_integral
    from graphics import animate, timestep_message
else:
    # Lines in triple quotes will be executed in the .pyx file.
    """
    from species cimport construct, construct_random
    from IO cimport load, save, load_gadget, save_gadget
    from integration cimport expand, cosmic_time, scalefactor_integral, ȧ
    from graphics cimport animate, timestep_message
    """

# Exit the program if called with the --exit flag
if int(sys.argv[2]):
    if master:
        os.system('printf "\033[1m\033[92mCO\033[3mN\033[0m\033[1m\033[92mCEPT'
                  + ' ran successfully\033[0m\n"')
    sys.exit()
# Load initial conditions
cython.declare(particles='Particles')
particles = load(IC_file)
# Check that the values in outputtimes are legal
if min(outputtimes) <= a_begin:
    raise Exception('The first snapshot is set at a = '
                    + str(min(outputtimes))
                    + ',\nbut the simulation starts at a = '
                    + str(a_begin) + '.')
if len(outputtimes) > len(set(outputtimes)):
    warn('Values in outputtimes are not unique.\n'
         + 'Extra values will be ignored.')


"""if master:
    print(a, np.mean(array(particles.posx_mw)[:4]),
             np.std(array(particles.posx_mw)[:4]),
             np.mean(array(particles.momx_mw)[:4]),
             np.std(array(particles.momx_mw)[:4]),
             np.mean(array(particles.posx_mw)[4:]),
             np.std(array(particles.posx_mw)[4:]),
             np.mean(array(particles.momx_mw)[4:]),
             np.std(array(particles.momx_mw)[4:]))"""

@cython.cfunc
@cython.cdivision(True)
@cython.boundscheck(False)
@cython.wraparound(True)  # Note legal wraparound!
@cython.locals(# Locals
               a='double',
               a_next='double',
               a_snapshot='double',
               i_snapshot='int',
               itg_drift0='double',
               itg_drift1='double',
               itg_kick0='double',
               itg_kick1='double',
               snapshot_filename='str',
               t='double',
               t_iter='double',
               timestep='size_t',
               Δt='double',
               )
def timeloop():
    # Initial cosmic time t, where a(t) = a_begin
    a = a_begin
    t = cosmic_time(a)
    # Plot the initial configuration
    animate(particles, 0, a, min(outputtimes))
    # The time step size should be a small fraction of the age of the universe
    Δt = Δt_factor*t
    # Arrays containing the drift and kick factors ∫_t^(t + Δt/2)dt/a
    # and ∫_t^(t + Δt/2)dt/a**2.
    drift_fac = empty(2)
    kick_fac = empty(2)
    # The main time loop (in actuality two nested loops)
    if master:
        print('Begin main time loop')
    timestep = 0
    t_iter = time()
    # Loop over all output snapshots
    for i_snapshot, a_snapshot in enumerate(sorted(set(outputtimes))):
        # The filename of the current snapshot
        snapshot_filename = (output_dir + '/' + snapshot_base
                             + '_' + str(i_snapshot))
        # Do the kick and drift intetrals
        # ∫_t^(t + Δt/2)dt/a and ∫_t^(t + Δt/2)dt/a**2.
        a = expand(a, t, 0.5*Δt)
        if a > a_snapshot:
            raise Exception('Finished time integration within a single step!')
        t += 0.5*Δt
        # This variable flip between 0 and 1, telling whether a kick or a drift
        # should be performed, respectively.
        kick_drift_index = 0
        # Do the kick and drift integrals
        # ∫_t^(t + Δt/2)dt/a and ∫_t^(t + Δt/2)dt/a**2.
        kick_fac[kick_drift_index] = scalefactor_integral(-1)
        drift_fac[kick_drift_index] = scalefactor_integral(-2)
        # The first, half kick
        particles.kick(kick_fac[kick_drift_index])
        # Leapfrog until a == a_snapshot
        while a < a_snapshot:
            # Update iteration timestamp, iteration number and time step size
            # every second iteration (every whole time step).
            if kick_drift_index:
                t_iter = time()
                timestep += 1
                Δt = Δt_factor*t
                # FLYT DET HER NEDERST SAMMEN MED DET ANDET. ÆNDRE SUM TIL 0 + 1
            # Flip the state of kick_drift_index
            kick_drift_index = 0 if kick_drift_index == 1 else 1
            # Update the scale factor and the cosmic time. This also tabulates
            # a(t), needed for the kick and drift integrals.
            a_next = expand(a, t, 0.5*Δt)
            t += 0.5*Δt
            if a_next >= a_snapshot:
                # Final step reached. A smaller time step than
                # Δt/2 is needed to hit a_snapshot exactly.
                t -= 0.5*Δt
                t_end = cosmic_time(a_snapshot, a, t, t + 0.5*Δt)
                expand(a, t, t_end - t)
                a_next = a_snapshot
                t = t_end
            a = a_next
            # Do the kick and drift integrals
            # ∫_t^(t + Δt/2)dt/a and ∫_t^(t + Δt/2)dt/a**2.
            kick_fac[kick_drift_index] = scalefactor_integral(-1)
            drift_fac[kick_drift_index] = scalefactor_integral(-2)
            # Perform drift or kick
            if kick_drift_index:
                # Drift a complete step, overtaking the kicks
                particles.drift(sum(drift_fac))
            else:
                # Kick a complete step, overtaking the drifts
                particles.kick(sum(kick_fac))
            # Dump snapshot if a == a_snapshot
            if a == a_snapshot:
                # Synchronize positions and momenta before dumping snapshot
                if kick_drift_index:
                    particles.kick(kick_fac[kick_drift_index])
                else:
                    particles.drift(drift_fac[kick_drift_index])
                # Dump snapshot
                save(particles, a, snapshot_filename)
            # Render particle configuration and print timestep message
            # every second iteration (every whole time step).
            if kick_drift_index:
                animate(particles, timestep, a, a_snapshot)
                timestep_message(timestep, t_iter, a, t)
            elif a == a_snapshot:
                animate(particles, timestep, a, a_snapshot)
    














        """while True:
            # Update iteration timestamp and number
            t_iter = time()
            timestep += 1
            # The time step size should be a small fraction
            # of the age of the universe.
            Δt = 0.01*t
            # Leapfrog drift
            if a == a_snapshot:
                # Last kick step reached a = a_snapshot.
                # Drift the remaining little bit to synchronize.
                particles.drift(itg_drift0)
                # Save snapshot and break out, beginning iteration
                # towards the next snapshot.
                save(particles, a, snapshot_filename)
                break
            else:
                # Do the kick and drift integrals
                # ∫_t^(t + Δt/2)dt/a and ∫_t^(t + Δt/2)dt/a**2.
                a_next = expand(a, t, 0.5*Δt)
                t += 0.5*Δt
                if a_next >= a_snapshot:
                    # Final step reached. A smaller time step than
                    # Δt/2 is needed to hit a_snapshot exactly.
                    t -= 0.5*Δt
                    t_end = cosmic_time(a_snapshot, a, t, t + 0.5*Δt)
                    expand(a, t, t_end - t)
                    a_next = a_snapshot
                    t = t_end
                a = a_next
                itg_kick1 = scalefactor_integral(-1)
                itg_drift1 = scalefactor_integral(-2)
                # Drift a complete step, overtaking the kicks
                particles.drift(itg_drift0 + itg_drift1)
            # Leapfrog kick
            if a == a_snapshot:
                # Last drift step reached a = a_snapshot.
                # Kick the remaining little bit to synchronize.
                particles.kick(itg_kick1)
                # Render particle configuration, print timestep message,
                # save snapshot and break out, beginning iteration towards the
                # next snapshot.
                animate(particles, timestep, a, a_snapshot)
                timestep_message(timestep, t_iter, a, t)
                save(particles, a, snapshot_filename)
                break
            else:
                # Do the kick and drift integrals
                # ∫_t^(t + Δt/2)dt/a and ∫_t^(t + Δt/2)dt/a**2.
                a_next = expand(a, t, 0.5*Δt)
                t += 0.5*Δt
                if a_next >= a_snapshot:
                    # Final step reached. A smaller time step than
                    # Δt/2 is needed to hit a_snapshot exactly.
                    t -= 0.5*Δt
                    t_end = cosmic_time(a_snapshot, a, t, t + 0.5*Δt)
                    expand(a, t, t_end - t)
                    a_next = a_snapshot
                    t = t_end
                a = a_next
                itg_kick0 = scalefactor_integral(-1)
                itg_drift0 = scalefactor_integral(-2)
                # Kick a complete step, overtaking the drifts
                particles.kick(itg_kick0 + itg_kick1)
                # Render particle configuration and print timestep message
                animate(particles, timestep, a, a_snapshot)
                timestep_message(timestep, t_iter, a, t)"""

# Run the time loop at import time
timeloop()
