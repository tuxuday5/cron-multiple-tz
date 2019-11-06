#!/usr/bin/python3
import re
import pytz
import calendar
import operator
import argparse
import sys

class InvalidCronEntryError(Exception):
    pass

class CronEntry():
    """ this is just a placeholder. so that related values to an entry 
    can be stored in a single var. enough of dict style ref."""
    def __init__(self,entry=None,serverTz=None,jobTz=None):
        self.entry = entry
        self.serverTz = serverTz
        self.jobTz =  jobTz
        self.ts    = None
        self.adjustedTs= None
        self.domHit = False
        self.dowHit = False

    def __str__(self):
        return "domHit {self.domHit} dowHit {self.dowHit} ts {self.ts} adjustedTs {self.adjustedTs}".format(self=self)


DEFAULT_VALUES = {
    'minute' : '',
    'hour' : '',
    'dom' : '',
    'month' : '',
    'dow' : '',
    'year' : '',
}

VALID_SPECIAL_STRINGS = [
    '@reboot',
    '@yearly',
    '@annually',
    '@monthly',
    '@weekly',
    '@daily',
    '@midnight',
    '@hourly',
]


REGEX_PATTERNS = {
    'server_tz' : re.compile('^#\s*SERVER_TZ='),
    'job_tz' : re.compile('^#\s*JOB_TZ='),
    'comment' : re.compile('^\s*#'),
    'blank_line' : re.compile('^\s*$'),
    'variable' : re.compile('^\s*\w+='),
    'parse_entry' : re.compile('\s'),
    'astreisk' : re.compile('^\s*\*\s*$'),
    'number' : re.compile('\d'),
    'range' : re.compile('-'),
    'list' : re.compile(','),
    'step' : re.compile('/'),
    'week_day_abbr' : re.compile('mon|tue|wed|thu|fri|sat|sun',re.I),
    'month_abbr' : re.compile('jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec',re.I)
}

ENTRY_ORDER = ['minute', 'hour', 'dom', 'month', 'dow', 'command']
ENTRY_TIME_FIELDS = [ 'month', 'dom', 'dow', 'hour', 'minute' ]
ENTRY_SORT_ORDER = [ 'month', 'dom', 'hour', 'minute', 'dow'] ## sort in this order
SQUEEZE_ORDER = [ 'minute', 'hour', 'dom', 'month', 'dow'] ## squeeze in this order
WEEK_DAY_SHORT_NAMES = []
MONTH_SHORT_NAMES = []

def SetWeekDayShortNames():
    global WEEK_DAY_SHORT_NAMES
    WEEK_DAY_SHORT_NAMES = []
    for i in range(7):
        WEEK_DAY_SHORT_NAMES.append(calendar.day_abbr[i].lower())

def SetMonthShortNames():
    global MONTH_SHORT_NAMES
    MONTH_SHORT_NAMES = []
    for i in range(1,12+1):
        MONTH_SHORT_NAMES.append(calendar.month_abbr[i].lower())

def GetMonthNoForShortName(inp):
    try:
        return MONTH_SHORT_NAMES.index(inp.lower())+1
    except ValueError:
        return -1

def GetWeekDayNoForShortName(inp):
    try:
        return WEEK_DAY_SHORT_NAMES.index(inp.lower())+1
    except ValueError:
        return -1

def SetDefaultValuesDomDow(entry):
    """modify global defaults based on entrie's dom/dow"""
    global DEFAULT_VALUES
    if REGEX_PATTERNS['astreisk'].match(entry['dom']) and REGEX_PATTERNS['astreisk'].match(entry['dow']):
        """lets use global defaults"""
        pass
    elif REGEX_PATTERNS['number'].search(entry['dom']) and REGEX_PATTERNS['number'].search(entry['dow']):
        """here its just default, actual values will be generated by routines further down"""
        pass
    elif REGEX_PATTERNS['number'].search(entry['dow']):
        """since dow will be set further down, we can clear dom"""
        DEFAULT_VALUES['dom'] = []
    elif REGEX_PATTERNS['number'].search(entry['dom']):
        """since dom will be set further down, we can clear dow"""
        DEFAULT_VALUES['dow'] = []
    else:
        pass

def SetDefaultValues():
    global DEFAULT_VALUES

    td = pytz.datetime.datetime.now()
    DEFAULT_VALUES['year'] = [td.year]
    DEFAULT_VALUES['minute'] = [x for x in range(0,59+1)]
    DEFAULT_VALUES['hour'] = [x for x in range(0,23+1)]
    DEFAULT_VALUES['month'] = [1] # for month it is ok.
    DEFAULT_VALUES['dom'] = [] # since its either dom/dow, we take default dow. 
    DEFAULT_VALUES['dow'] = [x for x in range(1,7+1)]

    return

def IsValidCronEntry(line):
    return True

def ParseCronEntry(line):
    """ break a cron entry into dict"""
    values = []

    entries = line.split()
    for entry in entries:
        if REGEX_PATTERNS['blank_line'].match(entry):
            continue
        elif len(values) < 5:
            values.append(entry)
        else:
            break

    values.append(' '.join(entries[5:]))

    return dict(zip(ENTRY_ORDER,values))

def ExpandRange(r,s=1):
    """expand 1-5 to [1..5], step by 1-10/2"""
    if REGEX_PATTERNS['step'].search(r):
        [r1,s] = r.split('/')
        s=int(s)
    else:
        r1 = r

    (start,end) = r1.split('-')
    return [i for i in range(int(start),int(end)+1,s)]

def NormalizeEntry(inp,stepStartVal=1):
    """ break range, 1-5, and list 1,2,3 into individual values"""
    expanded = []
    if REGEX_PATTERNS['list'].search(inp):
        for entry in inp.split(','):
            if REGEX_PATTERNS['range'].search(entry):
                expanded.extend(ExpandRange(entry))
            else:
                expanded.append(entry)
    elif REGEX_PATTERNS['range'].search(inp):
        expanded.extend(ExpandRange(inp))
    elif REGEX_PATTERNS['step'].search(inp):
        inp = str(stepStartVal) + '-' + inp
        expanded.extend(ExpandRange(inp))
    else:
        expanded = [ inp ] # expanded.append(inp) too will do

    retVal = []
    for x in expanded:
        try:
            retVal.append(int(x))
        except ValueError:
            pass

    return retVal

def ExpandMonths(inp):
    if REGEX_PATTERNS['astreisk'].match(inp):
        return DEFAULT_VALUES['month']
    elif REGEX_PATTERNS['month_abbr'].match(inp):
        if REGEX_PATTERNS['list'].search(inp):
            monthNames = inp.split(',')
            months = []
            for m in monthNames:
                months.append(str(GetMonthNoForShortName(m)))

            inp = ','.join(months)
        else:
            inp = str(GetMonthNoForShortName(inp))

    return NormalizeEntry(inp)

def ExpandDoM(inp):
    if REGEX_PATTERNS['astreisk'].match(inp):
        return DEFAULT_VALUES['dom']
    else:
        return NormalizeEntry(inp)

def ExpandDoW(inp):
    if REGEX_PATTERNS['astreisk'].match(inp):
        return DEFAULT_VALUES['dow']
    elif REGEX_PATTERNS['week_day_abbr'].match(inp):
        if REGEX_PATTERNS['list'].search(inp):
            wdNames = inp.split(',')
            wd = []
            for m in wdNames:
                wd.append(str(GetWeekDayNoForShortName(m)))

            inp = ','.join(wd)
        else:
            inp = str(GetWeekDayNoForShortName(inp))

    return NormalizeEntry(inp)

def ExpandHour(inp):
    if REGEX_PATTERNS['astreisk'].match(inp):
        return DEFAULT_VALUES['hour']
    else:
        return NormalizeEntry(inp,stepStartVal=0)

def ExpandMinutes(inp):
    if REGEX_PATTERNS['astreisk'].match(inp):
        return DEFAULT_VALUES['minute']
    else:
        return NormalizeEntry(inp,stepStartVal=0)

def GetEntryAsTimeStamps(record,tz):
    """ given a dict, rep a cron entry.
    convert in into datetime() - which can be used for tz adjustment
    this can for some instances generate 60*60*24*31/7 entries."""
    expandedTs = []

    year = DEFAULT_VALUES['year'][0]
    expandedMonth = ExpandMonths(record['month'])
    expandedDoW = ExpandDoW(record['dow'])

    expandedDoM = ExpandDoM(record['dom'])
    expandedHours = ExpandHour(record['hour'])
    expandedMins = ExpandMinutes(record['minute'])

    tsList = []
    for month in expandedMonth:
        """loop through all the days for specified months.
        if dom/dow is set, then add that datetime()"""
        for d in calendar.Calendar(firstweekday=1).itermonthdates(year,month):
            if d.month != month: #itermonthdates() returns complete weeks at beg,end
                continue 

            domHit = dowHit = False
            try:
                domHit = True if expandedDoM.index(d.day) >= 0 else False
            except ValueError:
                pass

            try:
                dowHit = True if expandedDoW.index(d.isoweekday()) >= 0 else False
            except ValueError:
                pass

            if domHit or dowHit:
                for hr in expandedHours:
                    for mins in expandedMins:
                        ts = pytz.datetime.datetime(d.year,d.month,d.day,hr,mins)
                        if ts in tsList:
                            continue
                        cronEntryObj = CronEntry(record,serverTz=tz)
                        cronEntryObj.ts = ts
                        cronEntryObj.dowHit = dowHit
                        cronEntryObj.domHit = domHit
                        tsList.append(ts)
                        expandedTs.append(cronEntryObj)

    return expandedTs

def AdjustForTz(record,serverTz,jobTz):
    """given a cron record, adjust for given tz"""
    expEntryObjs = GetEntryAsTimeStamps(record,serverTz)

    adjustedEntries = []
    utcTzObj = pytz.utc
    serverTzObj = pytz.timezone(serverTz)
    jobTzObj = pytz.timezone(jobTz)

    for entryObj in expEntryObjs:
        """to account for dst, always convert tz from utc
        http://pytz.sourceforge.net/
        """
        jobTs = jobTzObj.localize(entryObj.ts)
        utcTs = jobTs.astimezone(utcTzObj)
        entryObj.adjustedTs = utcTs.astimezone(serverTzObj)
        adjustedEntries.append(ReplaceEntryWithServerTs(entryObj))

    return adjustedEntries

def IsEntryNumberAlone(inp):
    pass

def ReplaceEntryWithServerTs(entryObj):
    """ entryObj. contains both actual cron entry and tz adjusted datetime()
    this function generates a tz adjusted cron entry.
    it applies lot of logic on how the out adjusted cron entry should be.
    it can get ugly for dom/dow especially"""
    retVal = {}

    entry = entryObj.entry
    serverTs = entryObj.adjustedTs

    retVal['command'] = entry['command']
    """min can't be copied to output as it is. ind-uk tz diff
    is 5.30hrs. so * might move from 30-59 of hour x & 0-29 hour x+1"""
    retVal['minute'] = str(serverTs.minute)

    if REGEX_PATTERNS['astreisk'].match(entry['hour']):
        retVal['hour'] = '*'
    else:
        retVal['hour'] = str(serverTs.hour)

    if REGEX_PATTERNS['astreisk'].match(entry['month']):
        retVal['month'] = '*'
    else:
        retVal['month'] = str(serverTs.month)

    if entryObj.domHit and entryObj.dowHit:
        """both dom & dow were configured in cron entry(dow can be from default too)
        if dow contains specific weekdays, 1-2 or 1,2,3 or *. then output dow should reflect that
        this is to help the SqueezeOnField* routines"""
        retVal['dom'] = str(serverTs.day)
        if REGEX_PATTERNS['range'].search(entry['dow']) \
                or REGEX_PATTERNS['list'].search(entry['dow']) \
                or REGEX_PATTERNS['astreisk'].match(entry['dow']):
            retVal['dow'] = entry['dow']
        else:
            retVal['dow'] = str(serverTs.isoweekday())
    elif entryObj.domHit:
        retVal['dom'] = str(serverTs.day)
        retVal['dow'] = entry['dow']
    elif entryObj.dowHit:
        if REGEX_PATTERNS['astreisk'].match(entry['month']):
            retVal['dom'] = entry['dom']
        else:
            """ for tz shift in mins. wrapping for next month
            * 20 3 30,31 1-7 for London->India produces 31st becomes first of next month
            30-59 1 3 31 1-7 #30th
            00-29 2 3 31 1-7 #30th
            30-59 0 4 1 1-7 #31st
            00-29 1 4 1 1-7 #31st
            """

            expandedMonth = ExpandMonths(entry['month'])
            if serverTs.month in expandedMonth:
                retVal['dom'] = str(serverTs.day)
            else:
                tzAdjustToNextMonth = False
                for m in expandedMonth:
                    if int(serverTs.month) == (m+1):
                        tzAdjustToNextMonth = True
                        break
                    else:
                        pass
                if tzAdjustToNextMonth:
                    retVal['dom'] = str(serverTs.day)
                else:
                    retVal['dom'] = entry['dom']

        if REGEX_PATTERNS['range'].search(entry['dow']) \
                or REGEX_PATTERNS['list'].search(entry['dow']) \
                or REGEX_PATTERNS['astreisk'].match(entry['dow']):
            retVal['dow'] = entry['dow']
        else:
            retVal['dow'] = str(serverTs.isoweekday())
    else:
        retVal['dom'] = '*'
        retVal['dow'] = '*'

    return retVal

def GetLineAsRecord(line):
    record = {}
    if IsValidCronEntry(line):
        return ParseCronEntry(line)
    else:
        raise InvalidCronEntryError(line)

def PrintLine(line,fileObj=sys.stdout,end="",flush=True):
    print(line,file=fileObj,end=end,flush=flush)

def PrintEntry(job,fileObj):
    for k in ENTRY_ORDER:
        PrintLine(job[k],fileObj=fileObj,end=' ',flush=False)

    PrintLine('',fileObj=fileObj,end="\n")

def GenerateSortKey(entry):
    """generate custom sort key based on ENTRY_SORT_ORDER"""
    key = ''

    for x in ENTRY_SORT_ORDER:
        if entry[x] == '*':
            key += '01'
        elif REGEX_PATTERNS['range'].search(entry[x]):
            key += '99'
        elif REGEX_PATTERNS['list'].search(entry[x]):
            key += '99'
        else:
            key += "{:02d}".format(int(entry[x]))

    return int(key)

def ConvertAsRangeIfPossible(val):
    """Used by SqueezeOnField* routines. given a list 1,2,3 convert to 1-3"""
    if not REGEX_PATTERNS['list'].search(val):
        return val

    vals = [int(v) for v in val.split(',')]
    v1 = vals[0]
    stepVal = vals[1]-vals[0]
    #stepVal = 1
    for v in vals[1:]:
        if v1+stepVal != v:
            return val
        else:
            v1 = v

    if v1 == vals[-1]:
        if stepVal == 1 or len(vals)==2:
            return "{0}-{1}".format(vals[0],vals[-1])
        else:
            return "{0}-{1}/{2}".format(vals[0],vals[-1],stepVal)
    else:
        return val


def EntryFieldsSame(e1,e2,fields):
    v1=tuple(e1[k] for k in fields)
    v2=tuple(e2[k] for k in fields)

    return v1==v2

def SqueezeOnFieldForTzShiftWithMins(entries,sqzField):
    """
    call this only after calling SqueezeOnField(),  GetUniqueEntries(), SqueezeOnField() 
    similar to SqueezeOnField(), but squeezes entries where tz shift is in mins too.
            30-59 1 3 30 1-7 
            00-29 2 3 30 1-7
            30-59 0 3 31 1-7 
            00-29 1 3 31 1-7

            will become
            30-59 0 3 30-31 1-7 
            00-29 1 3 30-31 1-7

    this routine does validtion to check the first 4 entries resemeble as above.
    if it does then proceeds to squeeze
    """
    if len(entries)<4:
        return entries

    if sqzField not in ENTRY_TIME_FIELDS:
        print("Given sqzField {0} not in ENTRY_TIME_FIELDS".format(sqzField),file=sys.stderr)
        return entries

    (prev1,prev2,cur1,cur2) = entries[0:4]

    if REGEX_PATTERNS['range'].search(prev1['minute']) and \
        REGEX_PATTERNS['range'].search(prev2['minute']) and \
        REGEX_PATTERNS['range'].search(cur1['minute']) and \
        REGEX_PATTERNS['range'].search(cur2['minute']):
        pass
    elif REGEX_PATTERNS['list'].search(prev1['minute']) and \
        REGEX_PATTERNS['list'].search(prev2['minute']) and \
        REGEX_PATTERNS['list'].search(cur1['minute']) and \
        REGEX_PATTERNS['list'].search(cur2['minute']):
        pass
    else:
        return entries

    try:
        if int(prev1['hour'])+1 == int(prev2['hour']) and \
                int(cur1['hour'])+1 == int(cur2['hour']):
            pass
        else:
            return entries
    except ValueError:
        """hour is list,range or astreisk"""
        return entries

    """only sqzField should inc, other fields should be same - so can squeezed"""
    otherThanSqzField = set(ENTRY_TIME_FIELDS).difference(('hour','minute',sqzField))
    tzShiftAdjInMinsFlag = False

    stepVal=1
    try:
        stepVal=int(cur1[sqzField]) - int(prev1[sqzField])
        if int(prev1[sqzField])+stepVal == int(cur1[sqzField]) and \
                int(prev2[sqzField])+stepVal == int(cur2[sqzField]):
            if EntryFieldsSame(prev1,cur1,otherThanSqzField) \
                and EntryFieldsSame(prev2,cur2,otherThanSqzField):
                tzShiftAdjInMinsFlag = True
            else:
                tzShiftAdjInMinsFlag = False
        else:
            tzShiftAdjInMinsFlag = False
    except ValueError:
        """sqzField is list,range or astreisk"""
        return entries

    if tzShiftAdjInMinsFlag == False:
        return entries

    squeezedEntries = []
    otherFields = ENTRY_TIME_FIELDS.copy()
    otherFields.remove(sqzField)

    prev1 = entries[0]
    squeeze1 = prev1.copy()

    prev2 = entries[1]
    squeeze2 = prev2.copy()

    stepVal=int(entries[2][sqzField]) - int(prev1[sqzField])

    curIdx = 2
    lastEntryAccounted = False
    totaEntries=len(entries)
    while curIdx+2 <= totaEntries:
        lastEntryAccounted = False
        canSqueeze = True

        cur1= entries[curIdx]
        cur2= entries[curIdx+1]

        if REGEX_PATTERNS['astreisk'].search(prev1[sqzField]) or \
            REGEX_PATTERNS['astreisk'].search(prev2[sqzField]) or \
            REGEX_PATTERNS['astreisk'].search(cur1[sqzField]) or \
            REGEX_PATTERNS['astreisk'].search(cur2[sqzField]):
            canSqueeze = False
        elif REGEX_PATTERNS['range'].search(prev1[sqzField]) or \
            REGEX_PATTERNS['range'].search(prev2[sqzField]) or \
            REGEX_PATTERNS['range'].search(cur1[sqzField]) or \
            REGEX_PATTERNS['range'].search(cur2[sqzField]):
            canSqueeze = False
        elif REGEX_PATTERNS['list'].search(prev1[sqzField]) or \
            REGEX_PATTERNS['list'].search(prev2[sqzField]) or \
            REGEX_PATTERNS['list'].search(cur1[sqzField]) or \
            REGEX_PATTERNS['list'].search(cur2[sqzField]):
            canSqueeze = False
        else:
            pass

        if canSqueeze == True:
            if int(prev1[sqzField])+stepVal == int(cur1[sqzField]) and \
                    int(prev2[sqzField])+stepVal == int(cur2[sqzField]):
                if EntryFieldsSame(prev1,cur1,otherFields) and \
                        EntryFieldsSame(prev2,cur2,otherFields):
                    squeeze1[sqzField] += ',' + cur1[sqzField]
                    squeeze2[sqzField] += ',' + cur2[sqzField]
                    prev1 = cur1
                    prev2 = cur2
                    lastEntryAccounted = True
                    curIdx+=2
                    continue
                else:
                    pass
            else:
                pass
        else:
            pass

        AppendToSqueezeList(squeezedEntries,sqzField,squeeze1,squeeze2)
        prev1 = cur1
        prev2 = cur2
        squeeze1 = prev1.copy()
        squeeze2 = prev2.copy()
        curIdx+=2

    if lastEntryAccounted:
        AppendToSqueezeList(squeezedEntries,sqzField,squeeze1,squeeze2)
    else:
        squeezedEntries.append(cur1)
        squeezedEntries.append(cur2)

    return squeezedEntries

def AppendToSqueezeList(li,sf,s1,s2=None):
    for s in (s1,s2):
        if s is None:
            continue
        s[sf] = ConvertAsRangeIfPossible(s[sf])
        li.append(s)

def SqueezeOnField(entries,sqzField):
    """entries are already sorted. 
    for n in entries:
        if n.sqzField = n+1.sqzField
         squeeze
        else
         can't squeeze, append this entry and continue
    """
    if len(entries)==1:
        return entries

    if sqzField not in ENTRY_TIME_FIELDS:
        print("Given sqzField {0} not in ENTRY_TIME_FIELDS".format(sqzField),file=sys.stderr)
        return entries

    squeezedEntries = []
    prev = entries[0]
    curSqueezeEntry = prev.copy()

    if REGEX_PATTERNS['astreisk'].match(prev[sqzField]) or \
            REGEX_PATTERNS['range'].search(prev[sqzField]) or \
            REGEX_PATTERNS['list'].search(prev[sqzField]):
        return entries

    otherFields = ENTRY_TIME_FIELDS.copy()
    otherFields.remove(sqzField)

    lastEntryAccounted = False
    stepVal = int(entries[1][sqzField]) - int(entries[0][sqzField])
    for cur in entries[1:]:
        lastEntryAccounted = False
        canSqueeze = True

        if REGEX_PATTERNS['astreisk'].match(prev[sqzField]) or \
                REGEX_PATTERNS['astreisk'].match(cur[sqzField]) or \
                REGEX_PATTERNS['range'].search(prev[sqzField]) or \
                REGEX_PATTERNS['range'].search(cur[sqzField]) or \
                REGEX_PATTERNS['list'].search(prev[sqzField]) or \
                REGEX_PATTERNS['list'].search(cur[sqzField]):
            canSqueeze = False
        else:
            pass

        if canSqueeze == True:
            if int(prev[sqzField])+stepVal == int(cur[sqzField]):
                if EntryFieldsSame(prev,cur,otherFields):
                    curSqueezeEntry[sqzField] += ',' + cur[sqzField]
                    prev = cur
                    lastEntryAccounted = True
                    continue
                else:
                    pass
            else:
                pass
        else:
            pass

        AppendToSqueezeList(squeezedEntries,sqzField,curSqueezeEntry)
        prev = cur
        curSqueezeEntry = prev.copy()

    if lastEntryAccounted:
        AppendToSqueezeList(squeezedEntries,sqzField,curSqueezeEntry)
    else:
        squeezedEntries.append(cur)

    return squeezedEntries
                
def GetUniqueEntries(entries):
    uniqueEntries = []
    for idx,rec in enumerate(entries):
        if rec not in entries[idx+1:]:
            uniqueEntries.append(rec)

    return uniqueEntries

def PrintEntriesForDebug(entries,msg=''):
    for x in entries:
        print("{msg}<>{month}.{dom}.{hour}.{minute}.{dow}".format(msg=msg,**x))

def Main(inFile,outFile=None):
    if outFile == None:
        outHand=sys.stdout
    else:
        outHand=open(outFile,'w')

    SetWeekDayShortNames()
    SetMonthShortNames()
    with open(inFile) as cronFileHandle:
        serverTz = ''
        jobTz = ''
        isJobTzSet = False
        for line in cronFileHandle:
            SetDefaultValues()
            if REGEX_PATTERNS['job_tz'].match(line):
                jobTz = line.split('=')[1].strip()
                isJobTzSet = True
    
            if REGEX_PATTERNS['server_tz'].match(line):
                serverTz = line.split('=')[1].strip()
                PrintLine(line,fileObj=outHand)
            elif REGEX_PATTERNS['comment'].match(line):
                PrintLine(line,fileObj=outHand)
            elif REGEX_PATTERNS['blank_line'].match(line):
                PrintLine(line,fileObj=outHand)
            elif REGEX_PATTERNS['variable'].match(line):
                PrintLine(line,fileObj=outHand)
            else:
                entryAsRecord = GetLineAsRecord(line)
                SetDefaultValuesDomDow(entryAsRecord)
                PrintLine(line,fileObj=outHand)

                if isJobTzSet:
                    #tzAdjustedEntryUnique = list(map(dict, frozenset(frozenset(tuple(e.items()) for e in tzAdjustedEntry))))
                    tzAdjustedEntry = AdjustForTz(entryAsRecord,serverTz,jobTz)

                    #PrintEntriesForDebug(tzAdjustedEntry,"AdjustedEntry")

                    tzAdjustedEntryUnique = GetUniqueEntries(tzAdjustedEntry)
                    tzAdjustedEntryUnique.sort(key=GenerateSortKey)

                    PrintLine('',fileObj=outHand,end="\n")
                    squeezedEntries = tzAdjustedEntryUnique

                    #PrintEntriesForDebug(tzAdjustedEntryUnique,"AdjustedEntryUnique")

                    for k in SQUEEZE_ORDER:
                        squeezedEntries = SqueezeOnField(squeezedEntries,k)

                    squeezedEntriesUnique = GetUniqueEntries(squeezedEntries)
                    squeezedEntriesUnique.sort(key=GenerateSortKey)

                    for k in SQUEEZE_ORDER:
                        squeezedEntriesUnique = SqueezeOnField(squeezedEntriesUnique,k)

                    #PrintEntriesForDebug(squeezedEntriesUnique,"squeezedEntriesUnique*2")
                    squeezedEntriesUnique2 = squeezedEntriesUnique

                    ## lets try squeezedEntriesUnique for tz shift with mins, like india-england
                    squeezedEntriesUnique2 = GetUniqueEntries(squeezedEntriesUnique)
                    squeezedEntriesUnique2.sort(key=GenerateSortKey)

                    squeezeKeysForTzShiftWithMins = SQUEEZE_ORDER.copy()
                    squeezeKeysForTzShiftWithMins.remove('minute')
                    squeezeKeysForTzShiftWithMins.remove('hour')
                    for k in squeezeKeysForTzShiftWithMins:
                        squeezedEntriesUnique2 = SqueezeOnFieldForTzShiftWithMins(squeezedEntriesUnique2,k)

                    for entry in squeezedEntriesUnique2:
                        PrintEntry(entry,fileObj=outHand)

                    isJobTzSet = False
                else:
                    PrintEntry(entryAsRecord,fileObj=outHand)


if __name__ == '__main__':
    argParser = argparse.ArgumentParser()
    argParser.add_argument('-i','--infile',type=str,required=True)
    argParser.add_argument('-o','--outfile',type=str,required=False)

    parsedArgs = vars(argParser.parse_args())
    Main(parsedArgs['infile'],outFile=parsedArgs['outfile'])
