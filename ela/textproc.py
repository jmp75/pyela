import string
import sys
import numpy as np
import pandas as pd
import scipy.stats.mstats as mstats
import re

from collections import Counter

import nltk
from nltk.corpus import stopwords


def remove_punctuations(text):
    for punctuation in string.punctuation:
        text = text.replace(punctuation, '')
    return text


LITHO_DESC_COL = 'Lithological Description'

PRIMARY_LITHO_COL = 'Lithology_1'
SECONDARY_LITHO_COL = 'Lithology_2'
PRIMARY_LITHO_NUM_COL = 'Lithology_1_num'
SECONDARY_LITHO_NUM_COL = 'Lithology_2_num'

DEPTH_FROM_COL = 'Depth From (m)'
DEPTH_TO_COL = 'Depth To (m)'
DEPTH_FROM_AHD_COL = 'Depth From (AHD)'
DEPTH_TO_AHD_COL = 'Depth To (AHD)'

EASTING_COL = 'Easting'
NORTHING_COL = 'Northing'

DISTANCE_COL = 'distance'
GEOMETRY_COL = 'geometry'

DEM_ELEVATION_COL = 'DEM_elevation'

WIN_SITE_ID_COL = 'WIN Site ID'



def v_find_primary_lithology(v_tokens, lithologies_dict):
    """Vectorised function to find a primary lithology in a list of tokenised sentences.

    Args:
        v_tokens (iterable of iterable of str): the list of tokenised sentences.
        lithologies_dict (dict): dictionary, where keys are exact markers as match for lithologies. Keys are the lithology classes. 

    Returns:
        list: list of primary lithologies if dectected. empty string for none.

    """
    return [find_primary_lithology(x, lithologies_dict) for x in v_tokens]

def v_find_secondary_lithology(v_tokens, prim_litho, lithologies_adjective_dict, lithologies_dict):
    """Vectorised function to find a secondary lithology in a list of tokenised sentences.

    Args:
        v_tokens (iterable of iterable of str): the list of tokenised sentences.
        prim_litho (list of str): the list of primary lithologies already detected for v_tokens. The secondary lithology cannot be the same as the primary.
        lithologies_adjective_dict (dict): dictionary, where keys are exact, "clear" markers for secondary lithologies (e.g. 'clayey'). Keys are the lithology classes. 
        lithologies_dict (dict): dictionary, where keys are exact markers as match for lithologies. Keys are the lithology classes.

    Returns:
        list: list of secondary lithologies if dectected. empty string for none.

    """
    if len(v_tokens) != len(prim_litho):
        raise Error('marker lithology tokens and their primary lithologies must be of same length')
    tokens_and_primary = [(v_tokens[i], prim_litho[i]) for i in range(len(prim_litho))]
    return [find_secondary_lithology(x, lithologies_adjective_dict, lithologies_dict) for x in tokens_and_primary]


def v_word_tokenize(descriptions): 
    """Vectorised tokenisation of lithology descriptions.

    Args:
        descriptions (iterable of str): lithology descriptions.

    Returns:
        list: list of lists of tokens in the NLTK.

    """
    return [nltk.word_tokenize(y) for y in descriptions]

v_lower = None
"""vectorised, unicode version to lower case strings

"""

if(sys.version_info.major > 2):
    v_lower = np.vectorize(str.lower)
    """vectorised, unicode version to lower case strings

    """
else:
    # Given Python 2.7 we must use:
    v_lower = np.vectorize(unicode.lower)
    """vectorised, unicode version to lower case strings

    """

def token_freq(tokens, n_most_common = 50):
    """Gets the most frequent (counts) tokens 

    Args:
        tokens (iterable of str): the list of tokens to analyse for frequence.
        n_most_common (int): subset to the this number of most frequend tokens

    Returns:
        pandas DataFrame: columns=["token","frequency"]

    """
    list_most_common=Counter(tokens).most_common(n_most_common)
    return pd.DataFrame(list_most_common, columns=["token","frequency"])

def plot_freq(dataframe, y_log = False, x='token', figsize=(15,10), fontsize=14):
    p = dataframe.plot.bar(x=x, figsize=figsize, fontsize=fontsize)
    if y_log:
        p.set_yscale("log", nonposy='clip')
    return p

def find_word_from_root(tokens, root):
    regex = re.compile('[a-z]*'+root+'[a-z]*')
    xx = list(filter(regex.search, tokens))
    return xx

def plot_freq_for_root(tokens, root, y_log=True):
    sand_terms = find_word_from_root(tokens, root)
    xf = token_freq(sand_terms, len(sand_terms))
    return plot_freq(xf, y_log=y_log)

def split_composite_term(x, joint_re):
    return re.sub("([a-z]+)(" + joint_re + ")([a-z]+)", r"\1 \2 \3", x, flags=re.DOTALL)

def split_with_term(x):
    return split_composite_term(x, 'with')

def v_split_with_term(xlist):
    return [split_with_term(x) for x in xlist]

def clean_lithology_descriptions(description_series, lex):
    expanded_descs = description_series.apply(lex.expand_abbreviations)
    y = expanded_descs.as_matrix()    
    y = v_lower(y)
    y = v_split_with_term(y)
    return y

def find_litho_markers(tokens, regex):
    return list(filter(regex.search, tokens))

def v_find_litho_markers(v_tokens, regex):
    return [find_litho_markers(t,regex) for t in v_tokens]


# I leave 'basalt' out, as it was mentioned it may be a mistake in the raw log data.
DEFAULT_LITHOLOGIES = ['sand','sandstone','clay','limestone','shale','coffee','silt','gravel','granite','soil','loam']

DEFAULT_ANY_LITHO_MARKERS_RE = r'sand|clay|ston|shale|basalt|coffee|silt|granit|soil|gravel|loam|mud|calca|calci'

DEFAULT_LITHOLOGIES_DICT = dict([(x,x) for x in DEFAULT_LITHOLOGIES])
DEFAULT_LITHOLOGIES_DICT['sands'] = 'sand'
DEFAULT_LITHOLOGIES_DICT['clays'] = 'clay'
DEFAULT_LITHOLOGIES_DICT['shales'] = 'shale'
DEFAULT_LITHOLOGIES_DICT['claystone'] = 'clay'
DEFAULT_LITHOLOGIES_DICT['siltstone'] = 'silt'
DEFAULT_LITHOLOGIES_DICT['limesand'] = 'sand' # ??
DEFAULT_LITHOLOGIES_DICT['calcarenite'] = 'limestone' # ??
DEFAULT_LITHOLOGIES_DICT['calcitareous'] = 'limestone' # ??
DEFAULT_LITHOLOGIES_DICT['mudstone'] = 'silt' # ??
DEFAULT_LITHOLOGIES_DICT['capstone'] = 'limestone' # ??
DEFAULT_LITHOLOGIES_DICT['ironstone'] = 'sandstone' # ??
DEFAULT_LITHOLOGIES_DICT['topsoil'] = 'soil' # ??

def find_primary_lithology(tokens, lithologies_dict):
    """Find a primary lithology in a tokenised sentence.

    Args:
        v_tokens (iterable of iterable of str): the list of tokenised sentences.
        lithologies_dict (dict): dictionary, where keys are exact markers as match for lithologies. Keys are the lithology classes. 

    Returns:
        list: list of primary lithologies if dectected. empty string for none.

    """
    keys = lithologies_dict.keys()
    for x in tokens:
        if x in keys:
            return lithologies_dict[x]
    return ''


DEFAULT_LITHOLOGIES_ADJECTIVE_DICT = {
    'sandy' :  'sand',
    'clayey' :  'clay',
    'clayish' :  'clay',
    'shaley' :  'shale',
    'silty' :  'silt',
    'gravelly' :  'gravel'
}

def find_secondary_lithology(tokens_and_primary, lithologies_adjective_dict, lithologies_dict):
    """Find a secondary lithology in a tokenised sentence.

    Args:
        tokens_and_primary (tuple ([str],str): tokens and the primary lithology
        lithologies_adjective_dict (dict): dictionary, where keys are exact, "clear" markers for secondary lithologies (e.g. 'clayey'). Keys are the lithology classes. 
        lithologies_dict (dict): dictionary, where keys are exact markers as match for lithologies. Keys are the lithology classes.

    Returns:
        str: secondary lithology if dectected. empty string for none.

    """
    tokens, prim_litho = tokens_and_primary
    if prim_litho == '': # cannot have a secondary lithology if no primary
        return ''
    # first, let's look at adjectives, more likely to semantically mean a secondary lithology
    keys = lithologies_adjective_dict.keys()
    for x in tokens:
        if x in keys:
            litho_class = lithologies_adjective_dict[x]
            if litho_class != prim_litho:
                return litho_class
    # then, as a fallback let's look at a looser set of terms to find a secondary lithology
    keys = lithologies_dict.keys()
    for x in tokens:
        if x in keys:
            litho_class = lithologies_dict[x]
            if litho_class != prim_litho:
                return litho_class
    return ''

