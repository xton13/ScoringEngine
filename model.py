import random
import copy
import db
import pickle
from threading import Thread

class Team(object):

    def __init__(self, id, name, subnet, netmask):
        self.id = id
        self.name = name
        self.subnet = subnet
        self.netmask = netmask

    def __str__(self):
        return self.name


class Credential(object):

    def __init__(self, id, username, password, team):
        self.id = id
        self.username = username
        self.password = password
        self.team = team

    def __str__(self):
        return "%s:%s:%s" % (self.team.name, self.username, self.password)


class Service(object):

    def __init__(self, id, host, port, checks):
        self.id = id
        self.host = host
        self.port = port
        self.checks = checks

    def check(self, teams):
        for check in self.checks:
            thread = Thread(target=check.check,
                            args=(teams, self.host, self.port))
            thread.start()

    def get_ip(self, subnet):
        octets = subnet.split('.')
        octets[3] = str(self.host)
        ip = '.'.join(octets)
        return ip

    def __str__(self):
        return "%s:%s" % (self.host, self.port)


class Check(object):

    def __init__(self, id, name, check_function, check_ios, poller):
        self.id = id
        self.name = name
        self.check_function = check_function
        self.check_ios = check_ios
        self.poller = poller

    def check(self, teams, host, port):
        check_io = random.choice(self.check_ios)
        poll_inputs = check_io.get_poll_inputs(teams, host, port)
        for poll_input in poll_inputs:
            thread = Thread(target=self.check_single,
                            args=(check_io.id, poll_input,check_io.expected))
            thread.start()

    def check_single(self, check_io_id, poll_input, expected):
        max_tries = 5 # TODO make this configurable
        tries = 0
        while tries < max_tries: 
            tries += 1
            poll_result = self.poller.poll(poll_input)
            if poll_result.exception is None:
                break
        result = self.check_function(poll_result, expected)
        team_id = poll_input.team.id
        self.store_result(check_io_id, team_id, poll_input,
                          poll_result, result)

    def store_result(self, check_io_id, team_id, poll_input,
                     poll_result, result):
        cmd = ("INSERT INTO result (check_id, check_io_id, team_id, "
	       "time, poll_input, poll_result, result) "
               "VALUES (%s, %s, %s, NOW(), %s, %s, %s)")
        poll_input = pickle.dumps(poll_input)
        poll_result = pickle.dumps(poll_result)
        db.execute(cmd, (self.id, check_io_id, team_id, 
                         poll_input, poll_result, result))


class CheckIO(object):
    
    def __init__(self, id, poll_input, expected, credentials):
        self.id = id
        self.poll_input = poll_input
        self.expected = expected
        self.credentials = credentials

    def get_poll_inputs(self, teams, host, port):
        if len(self.credentials) == 0:
            return self.get_poll_inputs_no_creds(teams, host, port)
        else:
            return self.get_poll_inputs_creds(teams, host, port)

    def get_poll_inputs_no_creds(self, teams, host, port):
        poll_inputs = []
        for team in teams:
            poll_input = self.make_poll_input(team, host, port)
            poll_inputs.append(poll_input)
        return poll_inputs

    def get_poll_inputs_creds(self, teams, host, port):
        poll_inputs = []
        credential = random.choice(self.credentials)
        creds = [cred for cred in self.credentials 
                 if cred.username == credential.username]
        for c in creds:
            team = c.team
            poll_input = self.make_poll_input(team, host, port)
            poll_input.credentials = c
            poll_inputs.append(poll_input)
        return poll_inputs

    def make_poll_input(self, team, host, port):
        poll_input = copy.copy(self.poll_input)
        server = self.check.service.get_ip(team.subnet)
        poll_input.server = server
        poll_input.port = port
        poll_input.team = team
        return poll_input


class Result(object):
    
    def __init__(self, result_id, check, check_io, team, 
                 time, poll_input, poll_result, result):
        self.result_id = result_id
        self.check = check
        self.check_io = check_io
        self.team = team
        self.time = time
        self.poll_input = poll_input
        self.poll_result = poll_result
        self.result = result
