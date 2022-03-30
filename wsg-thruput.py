#! /usr/bin/env python2.7
'''
   This script calculates the throughput per tunnel on a SAMI blade
   "Usage: ./wsg-thruput.py XRM_CA_02_WSG01"
   If you don't want to store your credentials in the script modify the lines

   USER = 'USERNAME'#raw_input('Username: ')
   PASS = 'PASSWORD'#getpass.getpass(prompt='Password: ')


'''
import getpass, paramiko, sys, re, time, signal

def signal_handler(sig, frame):
    print('Exiting gracefully Ctrl-C detected...')
    sys.exit()

def progress(count, total, status=''):
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write('[%s] %s%s ...%s\r' % (bar, percents, '%', status))
    sys.stdout.flush()

def connection_establishment(USER, PASS, host):
    try:
        print('Processing HOST: ' + host)
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, 22, username=USER, password=PASS)
        channel = client.invoke_shell()
        while not channel.recv_ready():
            time.sleep(0.5)

        output = channel.recv(8192)
    except paramiko.AuthenticationException as error:
        print ('Authentication Error on host: ' + host)
        exit()
    except IOError as error:
        print (error)
        exit()

    return (channel, client)

def connection_teardown(client):
   client.close()

def execute_command(command, channel):
    cbuffer = []
    data = ''

    channel.send(command)
    while True:
        if channel.recv_ready():
            data = channel.recv(1000)
            cbuffer.append(data)

        time.sleep(0.02)
        data_no_trails = data.strip()

        if len(data_no_trails) > 0: #and
            if (data_no_trails[-1] == '#'):
                break

    if channel.recv_ready():
        data = channel.recv(1000)
        cbuffer.append(data)

    rbuffer = ''.join(cbuffer)
    return (rbuffer)


def peer_list(IP):
    peer = []
    for i in range(1, len(IP)-1):
        peer.append(IP[i].strip().split(':')[2])

    return peer

def bytes_value(peer, channel):
    Bytes = []
    elements = []

    crypto = 'show crypto ipsec sa remote-ip' + peer + ' | be Bytes | i "Decrypted|Encrypted"\n'

    out = execute_command(crypto, channel)
    raw = out.split('\r\n')

    for j in range(1, 3):
        elements.append(raw[j].split(':')[1].strip())

    Bytes.append(elements)

    return Bytes

def bytes_encr_decr(IP, peer, channel):
    pastbytes = bytes_value(peer, channel)
    print pastbytes
    time.sleep(5)
    currentbytes = bytes_value(peer, channel)
    print currentbytes

    print "\r\nDecrypted throughput for IP", peer, ":", round(((int(currentbytes[0][0]) - int(pastbytes[0][0])) * 8) * 0.000001 / 5, 2), "Mbps"
    print "Encrypted throughput for IP", peer, ":", round(((int(currentbytes[0][1]) - int(pastbytes[0][1])) * 8) * 0.000001 / 5, 2), "Mbps"

def main():
    USER = raw_input('Username: ')
    PASS = getpass.getpass(prompt='Password: ')

    if len (sys.argv) != 2 :
        print "Usage: /wsg_throughput.py XRM_CA_02_WSG01"
        sys.exit (1)

    host = sys.argv[1]
    p = re.compile(r'X[A-Z]{2}_CA_0[12]_WSG[0-1][1-9]')
    if (not re.findall(p,sys.argv[1])):
        print "Check your hostname"
        sys.exit (1)

    SAMI = host[-2:]
    SECGW = host.replace('_', '-')[0:9]

    channel, client = connection_establishment(USER, PASS, SECGW)

    execute_command('session slot ' + SAMI + ' process 3\n', channel)
    print 'Connected to', host
    out = execute_command('sho crypto ha info\n', channel)

    if not re.findall('ACTIVE', out):
        print "Specified SAMI isn't active on this device"
        connection_teardown(client)
        sys.exit(1)

    execute_command('term len 0\n', channel)
    RemoteIP = execute_command('sho crypto isakmp sa | i "Remote IP"\n', channel)
    IP = RemoteIP.split('\r\n')

    peer = peer_list(IP)
    for i in range(0, len(peer)):
        bytes_encr_decr(IP, peer[i], channel)

    connection_teardown(client)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)  #catch ctrl-c and call handler to terminate the script
    main()
