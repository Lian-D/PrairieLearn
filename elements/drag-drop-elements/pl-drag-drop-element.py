import prairielearn as pl
import lxml.html
import random
import chevron
import base64
import os
import json

# Read https://prairielearn.readthedocs.io/en/latest/devElements/
# Official documentation on making custom PL


def render_html_colour(score):
    # used to render the correct colour depending on student score
    if score == 0:
        return 'badge-danger'
    elif score == 1.0:
        return 'badge-success'
    else:
        return 'badge-warning'

# courtesy of https://github.com/PrairieLearn/PrairieLearn/pull/2625


def getallAnswer(submitted_blocks, block_indents, leading_code, trailing_code):
    if len(submitted_blocks) == 0:
        return ''
    answer = ''
    for index, answer in enumerate(submitted_blocks):
        indent = int(block_indents[index])
        answer += ('    ' * indent) + submitted_blocks[index] + '\n'
    answer = leading_code + '\n' + answer + trailing_code + '\n'
    return answer


def gettarilAnswer(submitted_blocks, block_indents, trailing_code):
    if len(submitted_blocks) == 0:
        return ''
    answer = ''
    for index, answer in enumerate(submitted_blocks):
        indent = int(block_indents[index])
        answer += ('    ' * indent) + submitted_blocks[index] + '\n'
    answer = answer + trailing_code + '\n'
    return answer


def getleadAnswer(submitted_blocks, block_indents, leading_code):
    if len(submitted_blocks) == 0:
        return ''
    answer = ''
    for index, answer_indent in enumerate(block_indents):
        indent = int(answer_indent)
        answer += ('    ' * indent) + submitted_blocks[index] + '\n'
    answer = leading_code + '\n' + answer
    return answer


def render(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answerName = pl.get_string_attrib(element, 'answers-name')

    if data['panel'] == 'question':
        mcq_options = []   # stores MCQ options
        student_previous_submission = []
        submission_indent = []

        pl.check_attribs(element,
                         required_attribs=['answers-name'],
                         optional_attribs=['shuffle-options',
                                           'permutation-mode',
                                           'check-indentation',
                                           'header-left-column',
                                           'header-right-column',
                                           'external-grader',
                                           'file-name',
                                           'leading-code',
                                           'trailing-code'])

        for html_tags in element:
            if html_tags.tag == 'pl-answer':
                pl.check_attribs(html_tags, required_attribs=['correct'], optional_attribs=['ranking', 'indent'])
                mcq_options.append(str.strip(html_tags.text))   # store the original specified ordering of all the MCQ options

        answerName = pl.get_string_attrib(element, 'answers-name')
        header_left_column = pl.get_string_attrib(element, 'header-left-column', 'Drag from here:')
        header_right_column = pl.get_string_attrib(element, 'header-right-column', 'Construct your solution here:')

        student_submission_dict_list = []

        mcq_options = data['params'][answerName]

        if answerName in data['submitted_answers']:
            student_previous_submission = data['submitted_answers'][answerName]['student_raw_submission']
            mcq_options = list(set(mcq_options) - set(student_previous_submission))

        for index, mcq_options_text in enumerate(student_previous_submission):
            # render the answers column (restore the student submission)
            submission_indent = data['submitted_answers'][answerName]['student_answer_indent'][index]
            submission_indent = (int(submission_indent) * 50) + 5
            temp = {'text': mcq_options_text, 'indent': submission_indent}
            student_submission_dict_list.append(dict(temp))

        html_params = {
            'question': True,
            'answerName': answerName,
            'options': mcq_options,
            'header-left-column': header_left_column,
            'header-right-column': header_right_column,
            'submission_dict': student_submission_dict_list
        }

        with open('pl-drag-drop-element.mustache', 'r', encoding='utf-8') as f:
            html = chevron.render(f, html_params).strip()
        return html

    elif data['panel'] == 'submission':
        if pl.get_boolean_attrib(element, 'external-grader', False):
            return ''
        # render the submission panel
        uuid = pl.get_uuid()
        student_submission = ''
        colour = 'badge-danger'
        score = 0
        feedback = None

        if answerName in data['submitted_answers']:
            student_submission = data['submitted_answers'][answerName]['student_raw_submission']
        if answerName in data['partial_scores']:
            colour = render_html_colour(data['partial_scores'][answerName]['score'])
            score = data['partial_scores'][answerName]['score'] * 100
            feedback = data['partial_scores'][answerName]['feedback']

        html_params = {
            'submission': True,
            'uuid': uuid,
            'parse-error': data['format_errors'].get(answerName, None),
            'student_submission': student_submission,
            'colour': colour,
            'score': score,
            'perfect_score': True if score == 100 else None,
            'feedback': feedback
        }

        # Finally, render the HTML
        with open('pl-drag-drop-element.mustache', 'r', encoding='utf-8') as f:
            html = chevron.render(f, html_params).strip()
        return html

    elif data['panel'] == 'answer':
        if pl.get_boolean_attrib(element, 'external-grader', False):  # if True
            try:
                base_path = data['options']['question_path']
                file_lead_path = os.path.join(base_path, 'tests/ans.py')
                with open(file_lead_path, 'r') as file:
                    solution_file = file.read()
                return f'<pl-code language="python">{solution_file}</pl-code>'
            except FileNotFoundError:
                return 'The instructor did not include a reference solution. Try contacting them for the solution implementation?'

        permutationMode = pl.get_string_attrib(element, 'permutation-mode', 'html-order')
        permutationMode = ' in any order' if permutationMode == 'any' else 'in the specified order'

        if answerName in data['correct_answers']:
            html_params = {
                'true_answer': True,
                'question_solution': str(data['correct_answers'][answerName]['correct_answers']),
                'permutationMode': permutationMode
            }
            with open('pl-drag-drop-element.mustache', 'r', encoding='utf-8') as f:
                html = chevron.render(f, html_params).strip()
            return html
        else:
            return ''


def prepare(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answerName = pl.get_string_attrib(element, 'answers-name')

    mcq_options = []
    correct_answers = []
    correct_answers_indent = []

    isShuffle = pl.get_string_attrib(element, 'shuffle-options', 'false')  # default to FALSE, no shuffling unless otherwise specified

    for html_tags in element:
        if html_tags.tag == 'pl-answer':
            # CORRECT is optional for backward compatibility
            pl.check_attribs(html_tags, required_attribs=['correct'], optional_attribs=['ranking', 'indent'])
            mcq_options.append(str.strip(html_tags.text))   # store the original specified ordering of all the MCQ options

    if isShuffle == 'true':
        random.shuffle(mcq_options)

    for html_tags in element:
        if html_tags.tag == 'pl-answer':
            isCorrect = pl.get_string_attrib(html_tags, 'correct', 'false')  # default correctness to false
            answerIndent = pl.get_string_attrib(html_tags, 'indent', '-1')  # get answer indent, and default to -1 (indent level ignored)
            if isCorrect.lower() == 'true':
                # add option to the correct answer array, along with the correct required indent
                correct_answers.append(str.strip(html_tags.text))
                correct_answers_indent.append(answerIndent)

    data['params'][answerName] = mcq_options
    data['correct_answers'][answerName] = {'correct_answers': correct_answers,
                                           'correct_answers_indent': correct_answers_indent}


def parse(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answerName = pl.get_string_attrib(element, 'answers-name')

    temp = answerName
    temp += '-input'
    # the answerName textfields that raw-submitted-answer reads from
    # have '-input' appended to their name attribute

    student_answer_temp = ''
    if temp in data['raw_submitted_answers']:
        student_answer_temp = data['raw_submitted_answers'][temp]

    if student_answer_temp is None:
        data['format_errors'][answerName] = 'NULL was submitted as an answer!'
        return
    elif student_answer_temp == '':
        data['format_errors'][answerName] = 'No answer was submitted.'
        return

    student_answer = []
    student_answer_indent = []
    permutationMode = pl.get_string_attrib(element, 'permutation-mode', 'html-order')

    student_answer_ranking = ['Question permutationMode is not "ranking"']

    student_answer_temp = json.loads(student_answer_temp)

    student_answer = student_answer_temp['answers']
    student_answer_indent = student_answer_temp['answer_indent']

    if permutationMode.lower() == 'ranking':
        student_answer_ranking = []
        pl_drag_drop_element = lxml.html.fragment_fromstring(element_html)
        for answer in student_answer:
            e = pl_drag_drop_element.xpath(f'.//pl-answer[text()="{answer}"]')
            try:
                ranking = e[0].attrib['ranking']
            except IndexError:
                ranking = 0
            except KeyError:
                ranking = -1   # wrong answers have no ranking
            student_answer_ranking.append(ranking)

    if pl.get_boolean_attrib(element, 'external-grader', False):
        file_name = pl.get_string_attrib(element, 'file-name', None)
        leading_code = pl.get_string_attrib(element, 'leading-code', None)
        trailing_code = pl.get_string_attrib(element, 'trailing-code', None)
        base_path = data['options']['question_path']

        if leading_code is not None:
            file_lead_path = os.path.join(base_path, leading_code)
            with open(file_lead_path, 'r') as file:
                leadingnew_code = file.read()
        if trailing_code is not None:
            file_trail_path = os.path.join(base_path, trailing_code)
            with open(file_trail_path, 'r') as file:
                trailnewx_code = file.read()

        if file_name is not None:
            if leading_code is not None and trailing_code is not None:
                print('getallanswer')
                file_data = getallAnswer(student_answer, student_answer_indent, leadingnew_code, trailnewx_code)
            if leading_code is None and trailing_code is not None:
                print('get trail')
                file_data = gettarilAnswer(student_answer, student_answer_indent, trailnewx_code)
            if leading_code is not None and trailing_code is None:
                file_data = getleadAnswer(student_answer, student_answer_indent, leadingnew_code)
            data['submitted_answers']['_files'] = [{'name': file_name, 'contents': base64.b64encode(file_data.encode('utf-8')).decode('utf-8')}]

    data['submitted_answers'][answerName] = {'student_submission_ordering': student_answer_ranking,
                                             'student_raw_submission': student_answer,
                                             'student_answer_indent': student_answer_indent}
    if temp in data['submitted_answers']:
        del data['submitted_answers'][temp]


def grade(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answerName = pl.get_string_attrib(element, 'answers-name')

    student_answer = data['submitted_answers'][answerName]['student_raw_submission']
    student_answer_indent = data['submitted_answers'][answerName]['student_answer_indent']
    permutationMode = pl.get_string_attrib(element, 'permutation-mode', 'html-order')
    true_answer = data['correct_answers'][answerName]['correct_answers']
    true_answer_indent = data['correct_answers'][answerName]['correct_answers_indent']

    indent_score = 0
    final_score = 0
    feedback = ''

    if permutationMode == 'any':
        intersection = list(set(student_answer) & set(true_answer))
        final_score = float(len(intersection) / len(true_answer))
    elif permutationMode == 'html-order':
        final_score = 1.0 if student_answer == true_answer else 0.0
    elif permutationMode == 'ranking':
        ranking = data['submitted_answers'][answerName]['student_submission_ordering']
        correctness = 1
        partial_credit = 0
        if len(ranking) != 0 and len(ranking) == len(true_answer):
            if ranking[0] == 1:
                partial_credit = 1  # student will at least get 1 point for getting first element correct
            for x in range(0, len(ranking) - 1):
                if int(ranking[x]) == -1:
                    correctness = 0
                    break
                if int(ranking[x]) <= int(ranking[x + 1]):
                    correctness += 1
                else:
                    correctness = 0
                    break
        else:
            correctness = 0
        correctness = max(correctness, partial_credit)
        final_score = float(correctness / len(true_answer))

    check_indentation = pl.get_string_attrib(element, 'check-indentation', 'false')
    # check indents, and apply penalty if applicable
    if true_answer_indent.count('-1') != len(true_answer_indent) or check_indentation == 'true':
        for i, indent in enumerate(student_answer_indent):
            if indent == true_answer_indent[i] or true_answer_indent[i] == '-1':
                indent_score += 1
        final_score = final_score * (indent_score / len(true_answer_indent))

    data['partial_scores'][answerName] = {'score': final_score, 'feedback': feedback}


def test(element_html, data):
    element = lxml.html.fragment_fromstring(element_html)
    answerName = pl.get_string_attrib(element, 'answers-name')
    answerNameField = answerName + '-input'

    # incorrect and correct answer test cases
    # this creates the EXPECTED SUBMISSION field for test cases
    if data['test_type'] == 'correct':
        temp = data['correct_answers'][answerName]['correct_answers'].copy()  # temp array to hold the correct answers
        true_answer_indent = data['correct_answers'][answerName]['correct_answers_indent']
        for index, answer in enumerate(temp):
            temp[index] = answer + ':::' + true_answer_indent[index]
        data['raw_submitted_answers'][answerNameField] = ','.join(temp)
        data['partial_scores'][answerName] = {'score': 1, 'feedback': ''}
    elif data['test_type'] == 'incorrect':
        temp = data['correct_answers'][answerName]['correct_answers'].copy()  # temp array to hold the correct answers
        incorrect_answers = []
        for html_tags in element:
            if html_tags.tag == 'pl-answer':
                incorrect_answers.append(str.strip(html_tags.text))
        incorrect_answers = list(filter(lambda x: x not in temp, incorrect_answers))
        incorrect_answers = list(map(lambda x: x + ':::0', incorrect_answers))

        data['raw_submitted_answers'][answerNameField] = ','.join(incorrect_answers)
        data['partial_scores'][answerName] = {'score': 0, 'feedback': ''}

    elif data['test_type'] == 'invalid':
        data['raw_submitted_answers'][answerName] = 'bad input'
        data['format_errors'][answerName] = 'format error message'
    else:
        raise Exception('invalid result: %s' % data['test_type'])