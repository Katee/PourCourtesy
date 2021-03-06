import liblo
import sys
import serial
import time
import math

serial_wait_time_s = 0.05 
prev_timestamp_s   = 0

class Game:
    def __init__(self):
        self.players = [ Player(1), Player(2) ]
        self.waiting_for_headsets = True

    def tick(self, serial_conn):
        # Game has only two states on the server:
        # 1. Waiting for the players to put on their headsets properly
        # 2. Headsets are on properly and we're sending serial data to the arduino
    
        self._check_headsets()
        curr_timestamp_s = time.time()

        status_changed = False
        for player in self.players:
            if player.headset_status.status_changed:
                status_changed = True
                break
        if status_changed:
            print "Waiting for headsets..."
            for player in self.players:
                player.headset_status.status_print()
                player.headset_status.status_changed = False

        if not self.waiting_for_headsets:
            if serial_conn != None and serial_conn.isOpen():

                global prev_timestamp_s
                global serial_wait_time_s

                time_diff = curr_timestamp_s - prev_timestamp_s
                if time_diff >= serial_wait_time_s:

                    try:
                        out_str = "0"
                        serial_conn.write(chr(0))
                        for player in self.players:
                            serial_conn.write(player.serial_alpha())
                            serial_conn.write(player.serial_beta())
                            out_str += " " + str(ord(player.serial_alpha()))
                            out_str += " " + str(ord(player.serial_beta()))
                        serial_conn.flush()

                        print "Sent serial packet: " + out_str
                    except serial.SerialException as err:
                        print "Serial exception caught while writing. Serial connection will be reinitialized..."
                        print "Exception Details: ", err
                    except serial.SerialTimeoutException:
                        print "Serial write timed out. Serial connection will be reinitialized..."

                    prev_timestamp_s = curr_timestamp_s

    def _check_headsets(self):
        players_ready = True
        for player in self.players:
            if not player.headset_status.touching_forehead:
                players_ready = False
                break
       
        self.waiting_for_headsets = not players_ready

class Player:
    def __init__(self, playerNum):
        self.headset_status = HeadsetStatus(playerNum)
        self.alpha = [0,0,0,0]
        self.beta  = [0,0,0,0]

    def set_alpha(self, args):
        self.alpha[0], self.alpha[1], self.alpha[2], self.alpha[3] = args
        for i in range(0, 4):
            if math.isnan(self.alpha[i]):
                self.alpha[i] = 0

    def set_beta(self, args):
        self.beta[0], self.beta[1], self.beta[2], self.beta[3] = args
        for i in range(0, 4):
            if math.isnan(self.beta[i]):
                self.beta[i] = 0

    def serial_alpha(self):
        result = chr(0)
        try:
            temp   = float(sum(self.alpha)) / 4.0  # Avg. alpha
            temp   = min(1.0, (temp / 0.195))      # Scale the value
            result = chr(int(temp * 256))
        except:
            pass
        return result

    def serial_beta(self):
        result = chr(0)
        try:
            temp   = float(sum(self.beta)) / 4.0  # Avg. beta
            temp   = min(1.0, (temp / 0.195))     # Scale the value
            result = chr(int(temp * 256))
        except:
            pass
        return result

class HeadsetStatus:
    def __init__(self, playerNum):
        self.player_num  = playerNum
        self.left_ear    = "bad"
        self.left_front  = "bad"
        self.right_front = "bad"
        self.right_ear   = "bad"
        self.touching_forehead = False
        self.status_changed = True
    
    def is_good(self, num_accept_good):
        num_good = 0
        if self.left_ear == "good":
            num_good += 1
        if self.left_front == "good":
            num_good += 1
        if self.right_front == "good":
            num_good += 1
        if self.right_ear == "good":
            num_good += 1
        return num_good >= num_accept_good

    def update_with_horseshoe(self, args):
        self.left_ear, self.left_front, self.right_front, self.right_ear = args

    def update_with_touching_forehead(self, args):
        if self.touching_forehead != bool(args):
            self.status_changed = True
        self.touching_forehead = bool(args)
        
    def _status_num_to_readable(self, num):
        if num == 1:
            return "good"
        elif num == 2:
            return "ok"
        else:
            return "bad"

    def status_print(self):
        print "Player " + str(self.player_num) ,
        # + " Sensor Status (<left ear>, <left front>, <right front>, <right ear>):"
        #print self.left_ear + " " + self.left_front + " " + self.right_front + " " + self.right_ear
        print "Touching Forehead? " + str(self.touching_forehead)


# Globals
game    = Game()
servers = [ None, None ]

def status_callback(path, args, types, src, data):
    global game
    player_idx = data-1
    game.players[player_idx].headset_status.update_with_horseshoe(args)

def touching_forehead_callback(path, args, types, src, data):
    global game
    player_idx = data-1
    game.players[player_idx].headset_status.update_with_touching_forehead(args)

def alpha_callback(path, args, types, src, data):
    global game
    player_idx = data-1
    if game.players[player_idx].headset_status.touching_forehead:
        game.players[player_idx].set_alpha(args)

def beta_callback(path, args, types, src, data):
    global game
    player_idx = data-1
    if game.players[player_idx].headset_status.touching_forehead:
        game.players[player_idx].set_beta(args)

def connect_serial():
    serial_conn = None
    retryTime = 1.0
    while True:
        try:
            print "Opening serial connection..."
            serial_conn = serial.Serial(serial_port, baud_rate, timeout=3.0)
            if serial_conn.isOpen():
                break
            else:
                print "Failed to open serial connection, retrying in " + retryTime + " seconds..."

        except ValueError as e:
            print "Value Error: " + e.strerror
            exit(-1)

        except OSError as e:
            print "OS Error: " + e.strerror
            exit(-1)
    
        except serial.SerialException as e:
            print "Error setting up serial connection, retrying..."

        time.sleep(retryTime)
        retryTime = max(10.0, retryTime + 1.0)
    
    if serial_conn.isOpen():
        print "Serial connection open!"

    return serial_conn

if __name__ == "__main__":

    if len(sys.argv) < 5:
        print "Usage:"
        print "python " + sys.argv[0] + " <osc_port_muse_p1> <osc_port_muse_p2> <serial_port> <baud_rate>"
        sys.exit(0)
    
    # Open the OSC server, listening on the specified port
    try:
        servers[0] = liblo.Server(int(sys.argv[1]))
        servers[1] = liblo.Server(int(sys.argv[2]))
    except liblo.ServerError, err:
        print str(err)
        sys.exit()
    except ValueError:
        print "Ports must be a valid integers."
        sys.exit()

    count = 1
    for server in servers:
        server.add_method("/muse/dsp/elements/horseshoe", 'ffff', status_callback, count)
        server.add_method("/muse/dsp/elements/touching_forehead", 'i', touching_forehead_callback, count)
        server.add_method("/muse/dsp/elements/alpha", 'ffff', alpha_callback, count)
        server.add_method("/muse/dsp/elements/beta", 'ffff', beta_callback, count)
        count += 1
    
    serial_port = sys.argv[3]
    baud_rate   = sys.argv[4]
   
    # Attempt to connect to the serial
    serial_conn = connect_serial()

    while True:
        if (serial_conn is None) or (not serial_conn.isOpen()):
            serial_conn = connect_serial()
            
        for server in servers:
            server.recv(0)
        
        game.tick(serial_conn)
        
