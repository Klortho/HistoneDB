# -*- coding: utf-8 -*-
"""
Created on Thu Jun 13 13:09:07 2013

@author: alexeyshaytan
This script determines secondary structure elements of histone,
by algining it to reference sequences.

"""
#Standard Library
import argparse
import csv
import collections
import os
import re
import subprocess
import sys
import uuid
import cPickle as pickle
from StringIO import StringIO

#Required libraires
import pylab
import pandas as pd
import networkx as nx

#Django
from django.conf import settings 

#BioPython
from Bio import AlignIO
from Bio import Entrez
from Bio import ExPASy
from Bio import SeqIO
from Bio import SwissProt
from Bio.Align import MultipleSeqAlignment
from Bio.Align.AlignInfo import SummaryInfo
from Bio.Align.Applications import MuscleCommandline
from Bio.Alphabet import IUPAC
from Bio.Blast import NCBIXML
from Bio.Blast.Applications import NcbiblastpCommandline
from Bio.Emboss.Applications import NeedleCommandline
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.PDB.PDBParser import PDBParser
from Bio.PDB.Polypeptide import PPBuilder

Entrez.email = "eli.draizen@nih.gov"

#Let's define 1kx5 sequences
templ_H3 = Seq("ARTKQTARKSTGGKAPRKQLATKAARKSAPATGGVKKPHRYRPGTVALREIRRYQKSTELLIRKLPFQRLVREIAQDFKTDLRFQSSAVMALQEASEAYLVALFEDTNLCAIHAKRVTIMPKDIQLARRIRGERA", IUPAC.protein)
templ_H4 = Seq("SGRGKGGKGLGKGGAKRHRKVLRDNIQGITKPAIRRLARRGGVKRISGLIYEETRGVLKVFLENVIRDAVTYTEHAKRKTVTAMDVVYALKRQGRTLYGFGG", IUPAC.protein)
templ_H2A = Seq("SGRGKQGGKTRAKAKTRSSRAGLQFPVGRVHRLLRKGNYAERVGAGAPVYLAAVLEYLTAEILELAGNAARDNKKTRIIPRHLQLAVRNDEELNKLLGRVTIAQGGVLPNIQSVLLPKKTESSKSKSK", IUPAC.protein)
templ_H2B = Seq("AKSAPAPKKGSKKAVTKTQKKDGKKRRKTRKESYAIYVYKVLKQVHPDTGISSKAMSIMNSFVNDVFERIAGEASRLAHYNKRSTITSREIQTAVRLLLPGELAKHAVSEGTKAVTKYTSAK", IUPAC.protein)

#'element_name':[start,stop], start stop - are inclusive as in PDB file
#Numbering differes between symmetrical chains and 1kx5 vs 1aoi.
#We simply take the minimum length of alpha helices over all chains in 1kx5
#1 substructed from PDB values!!! because these values are in array index numberins starting from 0
ss_templ_H3 = {
    'alphaN':[43,56],
    'alpha1':[62,76],
    'alpha2':[84,113],
    'alpha3':[119,130],
    'loopL1':[78,83],
    'loopL2':[114,118],
    'beta1':[82,83],
    'beta2':[117,118],
    'mgarg1':[62,62],
    'mgarg2':[82,82],
    'mgarg3':[48,48]
}
ss_templ_H4 = {
    'alpha1ext':[23,28],
    'alpha1':[29,40],
    'alpha2':[48,75],
    'alpha3':[81,92],
    'loopL1':[41,47],
    'loopL2':[76,81],
    'beta1':[44,45],
    'beta2':[79,80],
    'beta3':[95,97],
    'mgarg1':[44,44]
}

#new def of docking domains as in Suto Luger 2000
ss_templ_H2A = {
    'alpha1ext':[15,21],
    'alpha1':[25,36],
    'alpha2':[45,72],
    'alpha3':[78,88],
    'alpha3ext':[89,96],
    'loopL1':[37,44],
    'loopL2':[73,77],
    'beta1':[41,42],
    'beta2':[76,77],
    'beta3':[99,101],
    'docking domain':[80,118],
    'mgarg1':[41,41],
    'mgarg2':[76,76]
}

ss_templ_H2B = {
    'alpha1':[33,45],
    'alpha2':[51,80],
    'alpha3':[86,98],
    'alphaC':[99,119],
    'loopL1':[46,50],
    'loopL2':[81,85],
    'beta1':[49,50],
    'beta2':[84,85],
    'mgarg1':[29,29]
}

ss_templ = {'H3':ss_templ_H3,'H4':ss_templ_H4,'H2A':ss_templ_H2A,'H2B':ss_templ_H2B}
templ = {'H3':templ_H3,'H4':templ_H4,'H2A':templ_H2A,'H2B':templ_H2B}

core_histones = [
    SeqRecord(templ_H3,id='H3',name='H3'),
    SeqRecord(templ_H4,id='H4',name='H4'),
    SeqRecord(templ_H2A,id='H2A',name='H2A'),
    SeqRecord(templ_H2B,id='H2B',name='H2B')
]

def get_hist_ss(test_seq, hist_type="Unknown", save_dir="", debug=True, save_alignment=False):
    """Returns sequence elements in histone sequence, all numbers assume first element in seq has number 0!!! Not like in PDB"""
    n2=str(uuid.uuid4())
    test_record = SeqRecord(test_seq, id='Query')
    

    ss_test = collections.defaultdict(lambda: [-1, -1])

    if hist_type == "H1":
        #H1 cannot be aligned becuase it does not share the histone fold
        if save_alignment:
            return None, ss_test, test_record
        return None, ss_test

    query_file = os.path.join(save_dir, "query_{}.fasta".format(n2))
    SeqIO.write(test_record, query_file, 'fasta')

    if hist_type == "Unknown":
        results_file = os.path.join(save_dir, "query_{}.xml".format(n2))
        blastp = os.path.join(os.path.dirname(sys.executable), "blastp")
        blastp_cline = NcbiblastpCommandline(
            cmd=blastp,
            query=query_file, 
            db=os.path.join(settings.STATIC_ROOT, "browse", "blast", "core_histones_1kx5.faa"), 
            evalue=10000000,
            outfmt=5, 
            out=results_file)
        stdout, stderr = blastp_cline()

        with open(result_file) as results:
            blast_results = [(alignment.title, hsp.expect, hsp) for blast_record in NCBIXML.parse(results) \
                for alignment in blast_record.alignments for hsp in alignment.hsps]

        #Cleanup
        os.remove(results_file)
        
        try:
            hist_identified, evalue, hsp = min(blast_results, key=lambda x:x[1])
            hist_identified = hist_identified.split()[1]
        except ValueError:
            #No best match
            os.remove(query_file)
            if save_alignment:
                return None, ss_test, test_record
            return None, ss_test


        if debug:
            print "Most likely this is histone:", hist_identified
            print hsp
    else:
        hist_identified = hist_type
    
    core_histone_query = os.path.join(settings.STATIC_ROOT, "browse", "blast", "{}.faa".format(hist_identified))

    needle_results = os.path.join(save_dir, "needle_{}.txt".format(n2))
    cmd = os.path.join(os.path.dirname(sys.executable), "needle")
    if not os.path.isfile(cmd):
        cmd = "needle"
    needle_cline = NeedleCommandline(
        cmd=cmd,
        asequence=core_histone_query, 
        bsequence=query_file, 
        gapopen=20, 
        gapextend=1, 
        outfile=needle_results)
    stdout, stderr = needle_cline()

    align = AlignIO.read(needle_results, "emboss")
    core_histone = align[0]
    query = align[1]

    hist = templ[hist_identified]

    corresponding_hist = range(len(hist))
    k=0
    for i, core_histone_postion in enumerate(core_histone):
        if core_histone_postion == "-":
            k += 1
        else:
            corresponding_hist[i-k]=i


    corresponding_test = range(len(test_seq))
    k=0
    for i, query_position in enumerate(query):
        if query_position == "-":
            k=k+1
        else:
            corresponding_test[i-k]=i


    for feature, (start, stop) in ss_templ[hist_identified].iteritems():
        start_in_aln = corresponding_hist[start]
        end_in_aln = corresponding_hist[stop]
        start_in_test_seq = -1
        end_in_test_seq = -1

        for k in xrange(len(core_histone)):
            try:
                start_in_test_seq = corresponding_test.index(start_in_aln+k)
                break
            except ValueError:
                continue

        for k in xrange(len(core_histone)):
            try:
                end_in_test_seq = corresponding_test.index(end_in_aln-k)
                break
            except ValueError:
                continue

        if start_in_test_seq == -1 or end_in_test_seq == -1 or start_in_test_seq > end_in_test_seq:
            ss_test[feature]=[-1,-1]
        else:
            ss_test[feature]=[start_in_test_seq,end_in_test_seq]

    ss_test["core"] = get_core_lendiff(ss_test, ss_templ[hist_identified])

    #Cleanup
    os.remove(query_file)
    os.remove(needle_results)
        
    if save_alignment:
        return hist_identified,ss_test,query

    return hist_identified,ss_test

def get_hist_ss_in_aln(alignment, hist_type='Unknown', save_dir="", debug=True, save_censesus=False):
    """Returns sequence elements in histone alignment, all numbers assume first element in seq has number 0!!! Not like in PDB"""

    #Let's extract consensus
    if(debug):
        print alignment
    a=SummaryInfo(alignment)
    cons=a.dumb_consensus(threshold=0.1, ambiguous='X')
    if(debug):
        print "Consensus"
        print cons
    hv, ss = get_hist_ss(cons,hist_type,save_dir,True)
    if save_censesus:
        return hv,ss,cons
    return hv,ss

def get_gff_from_align(alignment, outfile, hist_type='Unknown', save_dir="", debug=True):
    from browse.models import Sequence, Features
    hv,ss,cons=get_hist_ss_in_aln(alignment, hist_type, save_dir=save_dir, debug=debug, save_censesus=True)
    seq = Sequence(id="Consensus", sequence=cons.tostring())
    features = Features.from_dict(seq, ss)
    print >> outfile, features.full_gff()

def get_core_lendiff(test_ss,temp_ss,debug=0):
    """Returns ration of core length for test_seq versus template sequence"""
    #check 640798122
    len_t_core=max([ i[1] for i in temp_ss.values() ])-min([ i[0] for i in temp_ss.values() ])
    len_core=max([ i[1] for i in test_ss.values() ])-min([ i[0] for i in test_ss.values() ])
    if(debug):
        print "Template core length ", len_t_core
        print "Testseq core length ", len_core
    ratio=float(len_core)/float(len_t_core)
    return ratio

if __name__ == '__main__':

    H2A = Seq("SGRGKKKKKQGGKTRAKAKTRSSRAGLQFPVGRVHRLLRKGNYAERVGAGAPPPPPVYLAAVLEYLTAEILELAGNARRRRARDNKTTTTTTKTRIIPRHLQLAVRNDEELNKLLGRVTIAQGGVLPNIQSVLLPKKTESSKSKSK", IUPAC.protein)
    H2At = Seq("SGRGKQGGKTRAKAKTRSSRAGLQFPVGRVHRLLRKGNYAERVGAGAPVYLAAVLEYLTAEILELAGNAARDNKKTRIIPRHLQLAVRNDEELNKLLGRVTIAQGGVLPNIQSVLLPKKTESSKSKSK", IUPAC.protein)
    print get_hist_ss(H2At)
    # print get_core_lendiff(H2A,H2At)