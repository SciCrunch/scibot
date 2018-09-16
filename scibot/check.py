
def check_already_submitted(exact, exact_for_hypothesis, found_rrids, tags, unresolved_exacts):
    if exact in tags or exact_for_hypothesis in unresolved_exacts:
        print('\tskipping %s, already annotated' % exact)
        found_rrids[exact] = 'Already Annotated'
        return True

