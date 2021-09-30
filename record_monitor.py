import os
import numpy as np
import argparse
import subprocess

from time import time, sleep, localtime, strftime

# ------------------------------------------------------------------------------
# Arguments
# ------------------------------------------------------------------------------
parser = argparse.ArgumentParser(description='anesthesia-monitor')
parser.add_argument('--datadir', type=str, required=False,
                    default='/home/pi/Documents')
parser.add_argument('--repodir', type=str, required=False,
                    default=os.getcwd())
args = parser.parse_args()
datadir = args.datadir
repodir = args.repodir

recording_time = strftime("%Y-%m-%d-%H-%M-%S", localtime())
datadir = os.path.join(datadir, recording_time)

if os.path.isdir(datadir):
    raise ValueError('Recording directory already exists.')
else:
    os.mkdir(datadir)

# ------------------------------------------------------------------------------
# Start GA monitor
# ------------------------------------------------------------------------------
# Start monitor, remove any previous csv files
if os.path.isfile(os.path.join(repodir, 'AS3DataExport.csv')):
    os.system('rm ' + os.path.join(repodir, 'AS3DataExport.csv'))

if os.path.isfile(os.path.join(repodir, 'AS3Rawoutput1.raw')):
    os.system('rm ' + os.path.join(repodir, 'AS3Rawoutput1.raw'))

# Start up Datex Ohmeda S/5 monitor
# Error check here to see if /dev/ttyUSB0 is open (linux only)
dev_check = os.system('ls /dev/ttyUSB0')
if dev_check == 0:
    log_monitor = open(os.path.join(datadir, 'log-monitor.txt'), 'a')

    monitor = subprocess.Popen(["/usr/bin/mono",
                                os.path.join(repodir, "VSCapture.exe"),
                                "-port", "/dev/ttyUSB0",
                                "-interval", "5",
                                "-export", "1",
                                "-waveset", "0"],
                               stdout=log_monitor,
                               stderr=log_monitor)
    print('Monitor found at /dev/ttyUSB0')
else:
    raise IOError('No connected device found at /dev/ttyUSB0')

# List for holding monitor outputs
mr = [-1, -1, -1]

# Initial logging
log_ts = open(os.path.join(datadir, 'timestamps.txt'), 'a')
log_ts.close()
log_mac = open(os.path.join(datadir, 'ga-mac.txt'), 'a')
log_mac.close()
log_dose = open(os.path.join(datadir, 'dose.txt'), 'a')
log_dose.close()
log_o2 = open(os.path.join(datadir, 'oxygen.txt'), 'a')
log_o2.close()

# ------------------------------------------------------------------------------
# Run GA Monitor
# Only every 2.5 seconds. Check time since last sample, if >10 seconds,
# kill process and restart VSCapture
# ------------------------------------------------------------------------------
try:
    while True:
        t = time()

        if os.path.isfile(os.path.join(repodir, 'AS3DataExport.csv')):
            # Check if monitor hasn't produced a sample in 20 seconds
            if (time() - os.path.getmtime(os.path.join(repodir,
                                                       'AS3DataExport.csv'))) < 20:
                os.system('cp ' + os.path.join(repodir, 'AS3DataExport.csv') +
                          ' ' + os.path.join(datadir, 'AS3DataExport.csv'))
                os.system('cp ' + os.path.join(repodir, 'AS3Rawoutput1.raw') +
                          ' ' + os.path.join(datadir, 'AS3Rawoutput1.raw'))

                # Will return nan values for header strings
                mr = np.genfromtxt(os.path.join(repodir, 'AS3DataExport.csv'),
                                   skip_header=1,
                                   usecols=(9, 11, 8),
                                   delimiter=',')  # MAC, O2, Dose

                # Lazy numpy array check
                try:
                    mr = mr[-1, :]
                except:
                    pass
            else:
                # Kill monitor process and restart
                monitor.kill()

                dev_check = os.system('ls /dev/ttyUSB0')
                if dev_check == 0:
                    log_monitor.write('Monitor crash detected, killing process '
                                      'and restarting...\n')
                    print('Monitor crash detected, killing process and '
                          'restarting...')
                    monitor = subprocess.Popen(
                        ["/usr/bin/mono",
                         os.path.join(repodir, "VSCapture.exe"),
                         "-port", "/dev/ttyUSB0",
                         "-interval", "5",
                         "-export", "1",
                         "-waveset", "0"],
                        stdout=log_monitor,
                        stderr=log_monitor)
                else:
                    log_monitor.write('Monitor not responding, killing process. '
                                      '/dev/ttyUSB0 not found, monitor '
                                      'disconnected?\n')
                    raise IOError('Monitor not responding, killing process. '
                                  '/dev/ttyUSB0 not found, monitor disconnected?')

        else:
            # Monitor not writing correctly, check if /dev/ttyUSB0 exists
            mr = [-1, -1, -1]

        log_ts = open(os.path.join(datadir, 'timestamps.txt'), 'a')
        log_ts.write(str(t) + '\n')
        log_ts.close()

        log_mac = open(os.path.join(datadir, 'ga-mac.txt'), 'a')
        log_mac.write(str(mr[0]) + '\n')
        log_mac.close()

        log_dose = open(os.path.join(datadir, 'dose.txt'), 'a')
        log_dose.write(str(mr[2]) + '\n')
        log_dose.close()

        log_o2 = open(os.path.join(datadir, 'oxygen.txt'), 'a')
        log_o2.write(str(mr[1]) + '\n')
        log_o2.close()

        # Verbose output
        print(strftime("%m-%d-%Y %H:%M:%S (", localtime()) +
              '{:.1f}'.format(t) +
              '): O2 ' + str(mr[1]) +
              ', MAC ' + str(mr[0]) +
              ', Dose ' + str(mr[2]))

        sleep(2.5)
except KeyboardInterrupt:
    print('Ending recording session...')

# ------------------------------------------------------------------------------
# Clean up files and exit
# ------------------------------------------------------------------------------
os.system('mv ' + os.path.join(repodir, 'AS3DataExport.csv') +
          ' ' + os.path.join(datadir, 'AS3DataExport.csv'))
os.system('mv ' + os.path.join(repodir, 'AS3Rawoutput1.raw') +
          ' ' + os.path.join(datadir, 'AS3Rawoutput1.raw'))
monitor.kill()
log_monitor.close()

# Convert txt files to numpy arrays
for i in ['timestamps', 'oxygen', 'ga-mac', 'dose']:
    temp = np.loadtxt(os.path.join(datadir, i + '.txt'), dtype=float)
    np.save(os.path.join(datadir, i + '.npy'), temp)
print('All files converted.')
