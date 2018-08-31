# =COPYRIGHT=======================================================
# Licensed Materials - Property of IBM
#
# (c) Copyright IBM Corp. 2017, 2018 All Rights Reserved
#
# US Government Users Restricted Rights - Use, duplication or
# disclosure restricted by GSA ADP Schedule Contract with IBM Corp.
# =================================================================

import sys
import os
import logging
import re
import json

# Tokens
T_EOF            = 'T_EOF'
T_EOL            = 'T_EOL'
T_INT            = 'T_INT'
T_TEXT           = 'T_TEXT'
T_MD             = 'T_MD'
T_ASSIGN         = 'T_ASSIGN'
T_COMMENT        = 'T_COMMENT'
T_RBRACKET       = 'T_RBRACKET'
T_LBRACKET       = 'T_LBRACKET'
T_SINGLEQUOTE    = 'T_SINGLEQUOTE'
T_SEMICOLON      = 'T_SEMICOLON'
T_EQUALS         = 'T_EQUALS'
T_DOUBLEQUOTE    = 'T_DOUBLEQUOTE'
T_FULLSTOP       = 'T_FULLSTOP'
T_DECIMAL        = 'T_DECIMAL'
T_COMMENT        = 'T_COMMENT'
T_COMMA          = 'T_COMMA'
T_UNDERSCORE     = 'T_UNDERSCORE'
T_MINUS          = 'T_MINUS'
T_FORWARDSLASH   = 'T_FORWARDSLASH'
T_ATTRIBUTE      = 'T_ATTRIBUTE'
T_DATA           = 'T_DATA'
T_PLUS           = 'T_PLUS'
T_GT             = 'T_GT'
T_LT             = 'T_LT'
T_LBRACE         = 'T_LBRACE'
T_RBRACE         = 'T_RBRACE'
T_LCURLY         = 'T_LCURLY'
T_RCURLY         = 'T_RCURLY'
T_ATTRIBUTE      = 'T_ATTRIBUTE'
T_RECIPE_COMMENT = 'T_RECIPE_COMMENT'
T_BLOCK          = 'T_BLOCK'
T_NODE           = 'T_NODE'

#States
FIND_CHEF_ATTRIBUTE    = 'FIND_CHEF_ATTRIBUTE'
GET_METADATA           = 'GET_METADATA'
GET_DATA_LIST          = 'GET_DATA_LIST'
FIND_NODE              = 'FIND_NODE'
GET_ATTRIBUTE          = 'GET_ATTRIBUTE'

def _tokenise(text, token_regexs):

    pos = 0
    tokens = []
    while pos < len(text):
        match = None
        for token_regex in token_regexs:
            pattern, tag = token_regex
            regex = re.compile(pattern)
            match = regex.match(text, pos)
            if match:
                data = match.group(0)
                if tag:
                    token = (data, tag)
                    tokens.append(token)
                break
        if not match:
            sys.stderr.write('Illegal character: %s\n' % text[pos])
            sys.exit(1)
        else:
            pos = match.end(0)
    token = ('T_EOF', 'T_EOF')
    tokens.append(token)
    return tokens

def _seek(tokens, current_position, token, value=None):

    while current_position < len(tokens):
        if value is None:
            if tokens[current_position][1] == token:
                break
        else:
            if tokens[current_position][1] == token and tokens[current_position][0] == value:
                break
        if tokens[current_position][1] == T_EOF:
            break
        current_position = current_position + 1
    return current_position

def _eat(tokens, current_position, eat_tokens):

    while current_position < len(tokens):

        if tokens[current_position][1] in eat_tokens:
                current_position = current_position + 1
        else:
            break

        if tokens[current_position][1] == T_EOF:
            break

    return current_position

def _pop(tokens, current_position):

    if tokens[current_position][0] != T_EOF:
        return current_position + 1
    else:
        return current_position

def _key_exists(in_dict, in_list):

    my_dict = dict(in_dict)
    for list_key in in_list:
        if list_key in my_dict:
            my_dict = my_dict[list_key]
        else:
            return False
    return True

def _get_sub_dict(in_dict, in_list):

    my_dict = dict(in_dict)
    for list_key in in_list:
        if list_key in my_dict:
            my_dict = my_dict[list_key]

    in_list.pop()
    final_dict = {}
    for key in my_dict.keys():
        if not isinstance(my_dict[key], dict):
            temp_dict = _create_dict(in_list, key, my_dict[key])
            final_dict = _merge_dict(final_dict, temp_dict)
    return final_dict

def _create_dict(in_list, new_key, new_item):
    new_dict = {}
    new_list = list(in_list)
    if not new_list:
        final_item = {}
        final_item[new_key] = new_item
        return final_item
    else:
        key = new_list[0]
        new_list.pop(0)
        new_dict[key] = _create_dict(new_list, new_key, new_item)
    return new_dict

def _merge(org_item, new_item):
    org_type = type(org_item)
    new_type = type(new_item)
    if org_type != new_type:
        print('XXXXX ORGS DO NOT MATCH')

    fn = TYPE_MERGE_FNS.get(org_type, None)
    if fn:
        return fn(org_item, new_item)
    return new_item

def _merge_dict(org_dict, new_dict):
    mrg_dict = dict(org_dict)
    for key, item in new_dict.items():
        if key in mrg_dict:
            mrg_dict[key] = _merge(org_dict[key], new_dict[key])
        else:
            mrg_dict[key] = item
    return mrg_dict

def _merge_list(org_list, new_list):
    mrg_list = list(org_list)
    for item in new_list:
        if item not in mrg_list:
            mrg_list.append(item)
    return mrg_list

def print_dictionary(in_dict, spaces=0):

    print_dict = dict(in_dict)

    spaces = spaces + 2

    for key in print_dict.keys():
        if isinstance(print_dict[key], dict):
            print(spaces*' ' + key + ':')
            print_dictionary(print_dict[key], spaces)
        else:
            item = str(print_dict[key])
            print(spaces*' ' + key + ' : ' + item)

def _validate_metadata(recipe, recipe_attributes, recipe_attributes_internal, metadata_attributes, cookbook_name, spaces=0, attribute=None):

    recipe_dict = dict(recipe_attributes)
    errorfile = 'errorfile'

    spaces = spaces + 2
    exit_code = 0

    for key in recipe_dict.keys():
        if attribute == None:
            attribute = []
        if isinstance(recipe_dict[key], dict):
            attribute.append(key)
            if attribute[0] != cookbook_name:
                status = "          not required"
            elif _key_exists(metadata_attributes, attribute):
                status = "          found default.rb"
            elif _key_exists(recipe_attributes_internal, attribute):
                status = "          found internal.rb"
            else:
                status = "          ERROR NOTFOUND"
                open(errorfile, 'a').close()

            print(spaces*' ' + key + ': ' + status)
            _validate_metadata(recipe, recipe_dict[key], recipe_attributes_internal, metadata_attributes, cookbook_name, spaces, attribute)
            attribute.pop()
    if os.path.isfile(errorfile):
        return 1
    else:
        return 0

def validate_metadata(recipe_attributes, recipe_attributes_internal, metadata_attributes, cookbook_name, spaces=0):

    errorfile = 'errorfile'

    if os.path.exists(errorfile):
        os.remove(errorfile)

    errors = 0

    recipe_dict = dict(recipe_attributes)

    spaces = spaces + 2

    exit_code = 0

    for recipe in recipe_dict.keys():
        print "Processing " + recipe
        rc = _validate_metadata(recipe, recipe_dict[recipe], recipe_attributes_internal, metadata_attributes, cookbook_name, spaces)
        print rc
        if rc == 1:
            exit_code = 1
        print ''

    if os.path.exists(errorfile):
        os.remove(errorfile)

    return exit_code

def print_metadata_attributes(in_dict, met_file, attribute=None, printed=False, old_attribute=None):

    i = 0
    for key in sorted(in_dict.keys()):
        i = i + 1
        if isinstance(in_dict[key], dict):
            if attribute is None:
                attribute = key
            else:
                old_attribute=attribute
                attribute = attribute + '/' + key
            print_metadata_attributes(in_dict[key], met_file, attribute)
            attribute = old_attribute
        else:
            if not printed:
                met_file.write('attribute ' + '\'' + attribute + '\'' + ',\n')
                printed = True
            if isinstance(in_dict[key], list):
                met_file.write('          :' + key + ' => ' + str(in_dict[key]))
            else:
                met_file.write('          :' + key + ' => ' + '\'' + str(in_dict[key]) + '\'')
            if i < len(in_dict.keys()):
                met_file.write(',\n')
            else:
                met_file.write('\n')

def print_metadata_recipes(in_dict, met_file):

    for cookbook_name in sorted(in_dict.keys()):
        for recipe_name in sorted(in_dict[cookbook_name].keys()):
            met_file.write('recipe \'' + cookbook_name + '::' + recipe_name +'\', \'\n')
            for description in in_dict[cookbook_name][recipe_name]['description']:
                met_file.write(description + '\n')
            met_file.write('\'\n')

def get_chef_attribute_metadata(attribute_file):

    """

    get_chef_attribute_metadata will return a dictionary of attribtue metadata
    derived from a chef attribute file. The language is described in the
    chef_attributes.json file.

    :param str attribute_file: Full file path name of the attribute file.

    """

    token_regexs = [
        (r'[\r\n]+',                    T_EOL),
        (r'(?<=\')[A-Za-z0-9/{$][^\']*(?=\')', T_DATA),
        (r'(?<=\')[A-Za-z0-9/$][^\']*(?=\')', T_DATA),
        (r'(?<=\')[ A-Za-z0-9_?\!\&;~\\*^~%$\[\]\}\{,-\/\\.|?()@:+=.]*(?=\')', T_DATA),
        (r'\'\'', T_DATA),
        (r'[ \n\t]+',              None),
        (r'<md>',                  T_MD),
        (r'#',                     T_COMMENT),
        (r'\d+\.?\d+',             T_DECIMAL),
        (r'=>',                    T_ASSIGN),
        (r'<>',                    T_COMMENT),
        (r'\[',                    T_LBRACKET),
        (r'\]',                    T_RBRACKET),
        (r'\{',                    T_RBRACE),
        (r'\}',                    T_LBRACE),
        (r'\(',                    T_RCURLY),
        (r'\)',                    T_LCURLY),
        (r'\'',                    T_SINGLEQUOTE),
        (r'\:',                    T_SEMICOLON),
        (r'=',                     T_EQUALS),
        (r'\"',                    T_DOUBLEQUOTE),
        (r'\.',                    T_FULLSTOP),
        (r'\,',                    T_COMMA),
        (r'\_',                    T_UNDERSCORE),
        (r'\-',                    T_MINUS),
        (r'\/',                    T_FORWARDSLASH),
        (r'\+',                    T_PLUS),
        (r'\>',                    T_GT),
        (r'\<',                    T_LT),
        (r'[0-9]+',                T_INT),
        (r'[ A-Za-z|\!\&;?~\\*^~%$][A-Za-z0-9_?\!\&;~\\*^~%$@]*', T_TEXT),
    ]

    attribute_dictionary = {}
    dynamic_dictionary = {}

    file = open(attribute_file)
    text = file.read()
    file.close()

    tokens = _tokenise(text, token_regexs)

    current_position = 0
    current_state = FIND_CHEF_ATTRIBUTE

    while current_position < len(tokens):

        if current_state == FIND_CHEF_ATTRIBUTE:

            current_position = _seek(tokens, current_position, T_MD, '<md>')
            current_position = _pop(tokens, current_position)
            current_position = _eat(tokens, current_position,
                                    (T_SINGLEQUOTE, T_MD, T_EOL, T_COMMENT))

            current_position = _seek(tokens, current_position,
                                      T_TEXT, 'attribute')

            current_position = _pop(tokens, current_position)
            current_position = _eat(tokens, current_position, (T_SINGLEQUOTE,
                                                                T_MD, T_EOL,
                                                                T_COMMENT))

            current_position = _seek(tokens, current_position, T_DATA)

            if tokens[current_position][1] == T_DATA:
                current_path = tokens[current_position][0]
                current_state = GET_METADATA

            current_position = current_position + 1

        elif current_state == GET_METADATA:

            current_position = _seek(tokens, current_position, T_MD, '<md>')
            current_position = _pop(tokens, current_position)
            current_position = _eat(tokens, current_position, (T_SINGLEQUOTE,
                                                                T_MD, T_EOL,
                                                                T_SEMICOLON,
                                                                T_COMMENT))

            current_position = _seek(tokens, current_position, T_TEXT)

            if tokens[current_position][1] == T_TEXT:
                current_attribute = tokens[current_position][0]

            current_position = _seek(tokens, current_position, T_ASSIGN)
            current_position = _pop(tokens, current_position)
            current_position = _eat(tokens, current_position, (T_SINGLEQUOTE,
                                                                T_MD, T_EOL,
                                                                T_SEMICOLON,
                                                                T_COMMENT))
            if current_attribute == 'choice':
                current_data = []
                current_state = GET_DATA_LIST
                continue

            current_position = _seek(tokens, current_position, T_DATA)

            if tokens[current_position][1] == T_DATA:
                if tokens[current_position][0] == '\'\'':
                    current_data = ""
                else:
                    current_data = tokens[current_position][0]

            current_position = _pop(tokens, current_position)
            current_position = _eat(tokens, current_position, (T_SINGLEQUOTE))

            new_item = _create_dict(current_path.split('/'),
                                    current_attribute,
                                    current_data)

            if '$dynamicmaps' in current_path:
                dynamic_dictionary = _merge_dict(dynamic_dictionary,
                                                                  new_item)
            else:
                attribute_dictionary = _merge_dict(attribute_dictionary,
                                                                  new_item)

            if tokens[current_position][1] == T_COMMA:
                current_state = GET_METADATA
            else:
                current_state = FIND_CHEF_ATTRIBUTE

            current_position = current_position + 1

        elif current_state == GET_DATA_LIST:

            current_position = _seek(tokens, current_position, T_DATA)

            if tokens[current_position][1] == T_DATA and tokens[current_position][0].strip() != ',':
                current_data.append(tokens[current_position][0])

            if tokens[current_position+2][1] == T_RBRACKET:
                new_item = _create_dict(current_path.split('/'),
                                        current_attribute,
                                        current_data)
                new_item2 = _create_dict(current_path.split('/'),
                                        'options',
                                        current_data)
                attribute_dictionary = _merge_dict(attribute_dictionary,
                                                   new_item)
                attribute_dictionary = _merge_dict(attribute_dictionary,
                                                   new_item2)

                current_state = GET_METADATA

            current_position = current_position + 1

    return attribute_dictionary, dynamic_dictionary

def get_chef_recipe_attributes(recipes):

    token_regexs = [
        (r'node',                  T_NODE),
        (r'[\r\n]+',               T_EOL),
        (r'#',                     T_COMMENT),
        (r'(?<=\[)[\'][A-Za-z][A-Za-z0-9_\']*(?=\])', T_DATA),
        (r'[ \n\t]+',              None),
        (r'<md>',                  T_MD),
        (r'\d+\.?\d+',             T_DECIMAL),
        (r'=>',                    T_ASSIGN),
        (r'<>',                    T_COMMENT),
        (r'\[',                    T_LBRACKET),
        (r'\]',                    T_RBRACKET),
        (r'\{',                    T_RBRACE),
        (r'\}',                    T_LBRACE),
        (r'\(',                    T_RCURLY),
        (r'\)',                    T_LCURLY),
        (r'\'',                    T_SINGLEQUOTE),
        (r'\:',                    T_SEMICOLON),
        (r'=',                     T_EQUALS),
        (r'\"',                    T_DOUBLEQUOTE),
        (r'\.',                    T_FULLSTOP),
        (r'\,',                    T_COMMA),
        (r'\_',                    T_UNDERSCORE),
        (r'\-',                    T_MINUS),
        (r'\/',                    T_FORWARDSLASH),
        (r'\+',                    T_PLUS),
        (r'\>',                    T_GT),
        (r'\<',                    T_LT),
        (r'[0-9]+',                T_INT),
        (r'[ A-Za-z|\!\&;?~\\*^~%$][A-Za-z0-9_?\!\&;~\\*^~%$]*', T_TEXT),
    ]

    recipe_attributes = {}

    for recipe in recipes:

        recipe_file = open(recipe, "r")
        recipe_text = recipe_file.read()
        tokens = _tokenise(recipe_text, token_regexs)
        print 'Processing ' + recipe


        recipe_name = recipe.split(os.sep)[-1]
        cookbook_name = recipe.split(os.sep)[-3]

        current_position = 0
        current_state = FIND_NODE
        current_data = [recipe]

        while current_position < len(tokens):

            if current_state == FIND_NODE:

                current_position = _seek(tokens, current_position, T_NODE)
                current_state = GET_ATTRIBUTE

            if current_state == GET_ATTRIBUTE:

                current_position = _pop(tokens, current_position)
                current_position = _eat(tokens, current_position, (T_LBRACKET,
                                                                   T_RBRACKET,
                                                                   T_EOL))

                if tokens[current_position][1] == T_DATA:
                    current_data.append(tokens[current_position][0].strip('\''))
                    current_position = _eat(tokens, current_position, (T_LBRACKET,
                                                                       T_RBRACKET,
                                                                       T_EOL))
                else:
                    new_item = _create_dict(current_data, '', '')
                    recipe_attributes = _merge_dict(recipe_attributes, new_item)
                    current_data = [recipe]
                    current_state = FIND_NODE

            current_position = current_position + 1

        recipe_file.close()

    return recipe_attributes

def get_chef_recipe_attributes_internal(recipe):

    token_regexs = [
        (r'default',               T_NODE),
        (r'force_default',         T_NODE),
        (r'force_override',         T_NODE),
        (r'[\r\n]+',               T_EOL),
        (r'#',                     T_COMMENT),
        (r'(?<=\[)[\'][A-Za-z][A-Za-z0-9_\']*(?=\])', T_DATA),
        (r'[ \n\t]+',              None),
        (r'<md>',                  T_MD),
        (r'\d+\.?\d+',             T_DECIMAL),
        (r'=>',                    T_ASSIGN),
        (r'<>',                    T_COMMENT),
        (r'\[',                    T_LBRACKET),
        (r'\]',                    T_RBRACKET),
        (r'\{',                    T_RBRACE),
        (r'\}',                    T_LBRACE),
        (r'\(',                    T_RCURLY),
        (r'\)',                    T_LCURLY),
        (r'\'',                    T_SINGLEQUOTE),
        (r'\:',                    T_SEMICOLON),
        (r'=',                     T_EQUALS),
        (r'\"',                    T_DOUBLEQUOTE),
        (r'\.',                    T_FULLSTOP),
        (r'\,',                    T_COMMA),
        (r'\_',                    T_UNDERSCORE),
        (r'\-',                    T_MINUS),
        (r'\/',                    T_FORWARDSLASH),
        (r'\+',                    T_PLUS),
        (r'\>',                    T_GT),
        (r'\<',                    T_LT),
        (r'[0-9]+',                T_INT),
        (r'[ A-Za-z|\!\&;\\~*%^\$][A-Za-z0-9_?\!\&;\~\*%^\$]*', T_TEXT),
    ]

    recipe_attributes = {}

    recipe_file = open(recipe, "r")
    recipe_text = recipe_file.read()
    tokens = _tokenise(recipe_text, token_regexs)
    print 'Processing ' + recipe


    recipe_name = recipe.split(os.sep)[-1]
    cookbook_name = recipe.split(os.sep)[-3]

    current_position = 0
    current_state = FIND_NODE
    current_data = []

    while current_position < len(tokens):

        if current_state == FIND_NODE:

            current_position = _seek(tokens, current_position, T_NODE)
            current_state = GET_ATTRIBUTE

        if current_state == GET_ATTRIBUTE:

            current_position = _pop(tokens, current_position)
            current_position = _eat(tokens, current_position, (T_LBRACKET,
                                                               T_RBRACKET,
                                                               T_EOL))

            if tokens[current_position][1] == T_DATA:
                current_data.append(tokens[current_position][0].strip('\''))
                current_position = _eat(tokens, current_position, (T_LBRACKET,
                                                                   T_RBRACKET,
                                                                   T_EOL))
            else:
                new_item = _create_dict(current_data, '', '')
                recipe_attributes = _merge_dict(recipe_attributes, new_item)
                current_data = []
                current_state = FIND_NODE

        current_position = current_position + 1

        recipe_file.close()

    return recipe_attributes


def is_attribute_line(in_text):

    """

    is_attribute_line will return true/false depending on wether the attribute
    tag axists. It is designed to be run over the chef metadata.rb file.

    :param str in_line: A line of text.

    """

    token_regexs = [
        (r'[\r\n]+',                 T_EOL),
        (r'[ A-Za-z][A-Za-z0-9_/]*', T_TEXT),
        (r'.*', None),
    ]

    tokens = _tokenise(in_text, token_regexs)

    current_position = 0
    current_position = _seek(tokens, current_position, T_TEXT)

    if tokens[current_position][0] == 'attribute':
        return True
    elif tokens[current_position][0] == 'recipe':
        return True
    else:
        return False

def get_chef_role_metadata(roles):

    role_dictionary = {}
    for role_file in roles:
        file = open(role_file)
        role_json = json.load(file)
        file.close()

        #role_name = role_file.split(os.sep)[-1].strip('json').strip('.')
        if not 'name' in role_json: continue # skip
        role_name = role_json['name']

        new_item = {role_name: role_json}
        role_dictionary = _merge_dict(role_dictionary, new_item)

    return role_dictionary


def get_chef_recipe_metadata(recipes):

    token_regexs = [
        (r'[ \n\t]+',              None),
        (r'#<>', T_RECIPE_COMMENT),
        (r'# <>', T_RECIPE_COMMENT),
        (r'.*', T_TEXT),
    ]

    recipe_metadata = {}

    for recipe in recipes:

        recipe_description = []
        recipe_file = open(recipe, "r")
        recipe_text = recipe_file.read()
        tokens = _tokenise(recipe_text, token_regexs)

        recipe_name = recipe.split(os.sep)[-1]
        cookbook_name = recipe.split(os.sep)[-3]

        current_position = 0
        found_comment = False
        while current_position < len(tokens):

            current_position = _seek(tokens, current_position, T_RECIPE_COMMENT)
            if tokens[current_position][1] == T_RECIPE_COMMENT:
                current_position = _seek(tokens, current_position, T_TEXT)
                recipe_description.append(tokens[current_position][0])
            else:
                new_item = _create_dict([cookbook_name, recipe_name],
                                        'description',
                                        recipe_description)
                recipe_metadata = _merge_dict(recipe_metadata, new_item)
                recipe_description = []
                break

        current_position = current_position + 1
    recipe_file.close()
    return recipe_metadata

    temp_attributes = metadata_attributes

def write_attributes_json(metadata_attributes, attribute_file):


    #Firstly we massage the metadata to iron out the chef specific items
    #[required] - if 'recommended' the 'true ' else 'false'

    def _massage_attributes(in_dict, spaces=0):

        print_dict = in_dict
        for key in print_dict.keys():
            if isinstance(print_dict[key], dict):
                _massage_attributes(print_dict[key], spaces)
            else:
                if 'hidden' not in print_dict.keys():
                    print_dict['hidden'] = 'false'
                if key == 'required':
                    if print_dict[key] == 'recommended':
                        print_dict[key] = 'true'
                    else:
                        print_dict[key] = 'false'
                item = str(print_dict[key])

    _massage_attributes(metadata_attributes)

    json.dump(metadata_attributes, attribute_file,sort_keys=True, indent=4, separators=(',', ': '))

def write_recipes_json(recipe_attributes, recipe_file):

    json.dump(recipe_attributes, recipe_file,sort_keys=True, indent=4, separators=(',', ': '))

def write_components_json(metadata_components, dynamic_components, component_file, dump_components=[]):

    for component in sorted(metadata_components.keys()):

        temp_components = {}
        temp_dynamic = {}

        component_keys = metadata_components[component].keys()
        if len(component_keys) == 0:
           break
        if not 'depends_on' in component_keys:
            temp_components['depends_on'] = []
        else:
            depends_on = metadata_components[component]['depends_on']
            depends_on_list = []
            items = depends_on.split(",")
            for item in items:
                depends_on_list.append(item)

            temp_components['depends_on'] = depends_on_list

        if not 'objectname' in component_keys:
            temp_components['objectname'] = metadata_components[component]['name']
        else:
            temp_components['objectname'] = metadata_components[component]['name']

        if not 'displayname' in component_keys:
            temp_components['displayname'] = metadata_components[component]['name']
        else:
            temp_components['displayname'] = metadata_components[component]['displayname']

        temp_dynamic = _generate_dynamic(metadata_components[component]['default_attributes'], dynamic_components)
        if temp_dynamic:
            temp_components = _merge_dict(temp_components, temp_dynamic)
        temp_components['attributes'] = metadata_components[component]['default_attributes']
        temp_components['description'] = metadata_components[component]['description']
        temp_components['name'] = metadata_components[component]['name']

        temp_components['type'] = 'chef_role'
        temp_components['run_list'] = metadata_components[component]['run_list']
        dump_components.append(temp_components)

    json.dump(dump_components, component_file,sort_keys=True, indent=4, separators=(',', ': '))


def merge_json_to_dict(in_dict, json_file):


    file = open(json_file)
    json_data = json.load(file)
    file.close()
    if isinstance(json_data, dict):
        return _merge_dict(in_dict, json_data)
    elif isinstance(json_data, list):
        return _merge_list(in_dict, json_data)

def _generate_dynamic(role_attributes, dynamic_attributes, attribute1=None, attribute2=None):

    dynamic_dictionary = [0]
    dynamic_dictionary[0] = {}

    if attribute1 == None:
        attribute1 = []
    if attribute2 == None:
        attribute2 = []

    def _get_dynamic_attributes(role_attributes, dynamic_attributes, attribute1, attribute2):

        for key in sorted(dynamic_attributes.keys()):

            if isinstance(dynamic_attributes[key], dict):
                attribute1.append(key)
                if not key == '$dynamicmaps':
                    attribute2.append(key)
                if _key_exists(role_attributes, attribute2):
                    _get_dynamic_attributes(role_attributes, dynamic_attributes[key], attribute1, attribute2)
                if not attribute1[-1] == '$dynamicmaps':
                    attribute2.pop()
                attribute1.pop()
            else:
                temp_dict = _create_dict(attribute1, key, dynamic_attributes[key])
                dynamic_dictionary[0] = _merge_dict(dynamic_dictionary[0], temp_dict)


    _get_dynamic_attributes(role_attributes, dynamic_attributes, attribute1, attribute2)
    return dynamic_dictionary[0]

def _get_sub_dict(in_dict, in_list):

    my_dict = dict(in_dict)
    for list_key in in_list:
        if list_key in my_dict:
            my_dict = my_dict[list_key]

    in_list.pop()
    final_dict = {}
    for key in my_dict.keys():
        if not isinstance(my_dict[key], dict):
            temp_dict = _create_dict(in_list, key, my_dict[key])
            final_dict = _merge_dict(final_dict, temp_dict)
    return final_dict
TYPE_MERGE_FNS = {dict: _merge_dict, list: _merge_list}
