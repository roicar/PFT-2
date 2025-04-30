/*
 * PLUTO: An automatic parallelizer and locality optimizer
 * 
 * Copyright (C) 2007-2015 Uday Bondhugula
 *
 * This file is part of Pluto.
 *
 * Pluto is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3 of the License, or
 * (at your option) any later version.

 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * A copy of the GNU General Public Licence can be found in the file
 * `LICENSE' in the top-level directory of this distribution. 
 *
 */
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <getopt.h>
#include <libgen.h>

#include <unistd.h>
#include <sys/time.h>

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif


#include "osl/scop.h"
#include "osl/generic.h"
#include "osl/extensions/irregular.h"

#include "pluto.h"
#include "transforms.h"
#include "math_support.h"
#include "post_transform.h"
#include "program.h"
#include "version.h"

#include "clan/clan.h"
#include "candl/candl.h"
#include "candl/scop.h"
#define EAGER 0
#define LAZY 1

PlutoOptions *options;

void usage_message(void)
{
    fprintf(stdout, "Usage: polycc <input.c> [options] [-o output]\n");
    fprintf(stdout, "\nOptions:\n");
    fprintf(stdout, "       --isldep                  Use ISL-based dependence tester (enabled by default)\n");
    fprintf(stdout, "       --candldep                Use Candl as the dependence tester\n");
    fprintf(stdout, "       --[no]lastwriter          Remove transitive dependences (last conflicting access is computed for RAW/WAW)\n");
    fprintf(stdout, "                                 (disabled by default)\n");
    fprintf(stdout, "       --islsolve [default]      Use ISL as ILP solver (default)\n");
    fprintf(stdout, "       --pipsolve                Use PIP as ILP solver\n");
    fprintf(stdout, "       --glpk                    Use GLPK as ILP solver\n");
    fprintf(stdout, "\n");
    fprintf(stdout, "\n  Optimizations          Options related to optimization\n");
    fprintf(stdout, "       --tile                    Tile for locality [disabled by default]\n");
    fprintf(stdout, "       --[no]intratileopt        Optimize intra-tile execution order for locality [enabled by default]\n");
    fprintf(stdout, "       --l2tile                  Tile a second time (typically for L2 cache) [disabled by default] \n");
    fprintf(stdout, "       --parallel                Automatically parallelize (generate OpenMP pragmas) [disabled by default]\n");
    fprintf(stdout, "    or --parallelize\n");
    fprintf(stdout, "       --partlbtile              Enables one-dimensional concurrent start (recommended)\n");
    fprintf(stdout, "    or --part-diamond-tile\n");
    fprintf(stdout, "       --lbtile                  Enables full-dimensional concurrent start\n");
    fprintf(stdout, "    or --diamond-tile\n");
    fprintf(stdout, "       --[no]prevector           Mark loops for (icc/gcc) vectorization (enabled by default)\n");
    fprintf(stdout, "       --multipar                Extract all degrees of parallelism [disabled by default];\n");
    fprintf(stdout, "                                    by default one degree is extracted within any schedule sub-tree (if it exists)\n");
    fprintf(stdout, "       --innerpar                Choose pure inner parallelism over pipelined/wavefront parallelism [disabled by default]\n");
    fprintf(stdout, "\n   Fusion                Options to control fusion heuristic\n");
    fprintf(stdout, "       --nofuse                  Do not fuse across SCCs of data dependence graph\n");
    fprintf(stdout, "       --maxfuse                 Maximal fusion\n");
    fprintf(stdout, "       --smartfuse [default]     Heuristic (in between nofuse and maxfuse)\n");
    fprintf(stdout, "\n   Index Set Splitting        \n");
    fprintf(stdout, "       --iss                  \n");
    fprintf(stdout, "\n   Code generation       Options to control Cloog code generation\n");
    fprintf(stdout, "       --nocloogbacktrack        Do not call Cloog with backtrack (default - backtrack)\n");
    fprintf(stdout, "       --cloogsh                 Ask Cloog to use simple convex hull (default - off)\n");
    fprintf(stdout, "       --codegen-context=<value> Parameters are at least as much as <value>\n");
    fprintf(stdout, "\n   Miscellaneous\n");
    fprintf(stdout, "       --rar                     Consider RAR dependences too (disabled by default)\n");
    fprintf(stdout, "       --[no]unroll              Unroll-jam (disabled by default)\n");
    fprintf(stdout, "       --ufactor=<factor>        Unroll-jam factor (default is 8)\n");
    fprintf(stdout, "       --forceparallel=<bitvec>  6 bit-vector of depths (1-indexed) to force parallel (0th bit represents depth 1)\n");
    fprintf(stdout, "       --readscop                Read input from a scoplib file\n");
    fprintf(stdout, "       --bee                     Generate pragmas for Bee+Cl@k\n\n");
    fprintf(stdout, "       --indent  | -i            Indent generated code (disabled by default)\n");
    fprintf(stdout, "       --silent  | -q            Silent mode; no output as long as everything goes fine (disabled by default)\n");
    fprintf(stdout, "       --help    | -h            Print this help menu\n");
    fprintf(stdout, "       --version | -v            Display version number\n");
    fprintf(stdout, "\n   Debugging\n");
    fprintf(stdout, "       --debug                   Verbose/debug output\n");
    fprintf(stdout, "       --moredebug               More verbose/debug output\n");
    fprintf(stdout, "\nTo report bugs, please email <pluto-development@googlegroups.com>\n\n");
}

static double rtclock()
{
    struct timezone Tzp;
    struct timeval Tp;
    int stat;
    stat = gettimeofday (&Tp, &Tzp);
    if (stat != 0) printf("Error return from gettimeofday: %d",stat);
    return(Tp.tv_sec + Tp.tv_usec*1.0e-6);
}

int main(int argc, char *argv[])
{
    int i;

    double t_start, t_c, t_d, t_t, t_all, t_start_all;

    t_c = 0.0;

    t_start_all = rtclock();

    FILE *src_fp;

    int option;
    int option_index = 0;

    int nolastwriter = 0;

    char *srcFileName;
    char *inputfilename;
    inputfilename = NULL;
    FILE *cloogfp, *outfp;

    if (argc <= 1)  {
        usage_message();
        return 1;
    }

    options = pluto_options_alloc();

    const struct option pluto_options[] =
    {
        {"tile", no_argument, &options->tile, 1},
        {"notile", no_argument, &options->tile, 0},
        {"intratileopt", no_argument, &options->intratileopt, 1},
        {"nointratileopt", no_argument, &options->intratileopt, 0},
        {"lbtile", no_argument, &options->lbtile, 1},
        {"diamond-tile", no_argument, &options->lbtile, 1},
        {"part-diamond-tile", no_argument, &options->partlbtile, 1},
        {"partlbtile", no_argument, &options->partlbtile, 1},
        {"debug", no_argument, &options->debug, true},
        {"moredebug", no_argument, &options->moredebug, true},
        {"rar", no_argument, &options->rar, 1},
        {"identity", no_argument, &options->identity, 1},
        {"nofuse", no_argument, &options->fuse, NO_FUSE},
        {"maxfuse", no_argument, &options->fuse, MAXIMAL_FUSE},
        {"smartfuse", no_argument, &options->fuse, SMART_FUSE},
        {"parallel", no_argument, &options->parallel, 1},
        {"parallelize", no_argument, &options->parallel, 1},
        {"innerpar", no_argument, &options->innerpar, 1},
        {"iss", no_argument, &options->iss, 1},
        {"unroll", no_argument, &options->unroll, 1},
        {"nounroll", no_argument, &options->unroll, 0},
        {"polyunroll", no_argument, &options->polyunroll, 1},
        {"bee", no_argument, &options->bee, 1},
        {"ufactor", required_argument, 0, 'u'},
        {"prevector", no_argument, &options->prevector, 1},
        {"noprevector", no_argument, &options->prevector, 0},
        {"codegen-context", required_argument, 0, 'c'},
        {"coeff-bound", required_argument, 0, 'C'},
        {"cloogf", required_argument, 0, 'F'},
        {"cloogl", required_argument, 0, 'L'},
        {"cloogsh", no_argument, &options->cloogsh, 1},
        {"nocloogbacktrack", no_argument, &options->cloogbacktrack, 0},
        {"forceparallel", required_argument, 0, 'p'},
        {"ft", required_argument, 0, 'f'},
        {"lt", required_argument, 0, 'l'},
        {"multipar", no_argument, &options->multipar, 1},
        {"l2tile", no_argument, &options->l2tile, 1},
        {"version", no_argument, 0, 'v'},
        {"help", no_argument, 0, 'h'},
        {"indent", no_argument, 0, 'i'},
        {"silent", no_argument, &options->silent, 1},
        {"lastwriter", no_argument, &options->lastwriter, 1},
        {"nolastwriter", no_argument, &nolastwriter, 1},
        {"nodepbound", no_argument, &options->nodepbound, 1},
        {"scalpriv", no_argument, &options->scalpriv, 1},
        {"isldep", no_argument, &options->isldep, 1},
        {"candldep", no_argument, &options->candldep, 1},
        {"isldepaccesswise", no_argument, &options->isldepaccesswise, 1},
        {"isldepstmtwise", no_argument, &options->isldepaccesswise, 0},
        {"noisldepcoalesce", no_argument, &options->isldepcoalesce, 0},
        {"readscop", no_argument, &options->readscop, 1},
        {"pipsolve", no_argument, &options->pipsolve, 1},
        {"islsolve", no_argument, &options->islsolve, 1},
        {"time", no_argument, &options->time, 1},
        {"inputfilename",required_argument,0,'N'},
        {"ifreplace",no_argument,&options->ifreplace,1},
        {0, 0, 0, 0}
    };


    /* Read command-line options */
    while (1) {
        option = getopt_long(argc, argv, "bhiqvf:l:F:L:c:o:N", pluto_options,
                &option_index);

        if (option == -1)   {
            break;
        }

        switch (option) {
            case 0:
                break;
            case 'F':
                options->cloogf = atoi(optarg);
                break;
            case 'L':
                options->cloogl = atoi(optarg);
                break;
            case 'b':
                options->bee = 1;
                break;
            case 'c':
                options->codegen_context = atoi(optarg);
                break;
            case 'C':
                options->coeff_bound = atoi(optarg);
                if (options->coeff_bound <= 0) {
                    printf("ERROR: coeff-bound should be at least 1\n");
                    return 2;
                }
                break;
            case 'd':
                break;
            case 'f':
                options->ft = atoi(optarg);
                break;
            case 'g':
                break;
            case 'h':
                usage_message();
                return 2;
            case 'i':
                /* Handled in polycc */
                break;
            case 'l':
                options->lt = atoi(optarg);
                break;
            case 'm':
                break;
            case 'n':
                break;
            case 'o':
                options->out_file = strdup(optarg);
                break;
            case 'p':
                options->forceparallel = atoi(optarg);
                break;
            case 'q':
                options->silent = 1;
                break;
            case 's':
                break;
            case 'u':
                options->ufactor = atoi(optarg);
                break;
            case 'N':
                inputfilename = optarg;
                printf("%s",inputfilename);
                break;
            case 'v':
            

                printf("PLUTO %s - An automatic parallelizer and locality optimizer\n\
Copyright (C) 2007--2008  Uday Kumar Bondhugula\n\
This is free software; see the source for copying conditions.  There is NO\n\
warranty; not even for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.\n\n", PLUTO_VERSION);
                pluto_options_free(options);
                return 3;
            default:
                usage_message();
                pluto_options_free(options);
                return 4;
        }
    }

    if (optind <= argc-1)   {
        srcFileName = alloca(strlen(argv[optind])+1);
        strcpy(srcFileName, argv[optind]);
    }else{
        /* No non-option argument was specified */
        usage_message();
        pluto_options_free(options);
        return 5;
    }

    /* Make options consistent */
    if (options->isldep && options->candldep) {
        printf("[pluto] ERROR: only one of isldep and candldep should be specified)\n");
        pluto_options_free(options);
        usage_message();
        return 1;
    }

    /* isldep is the default */
    if (!options->isldep && !options->candldep) {
        options->isldep = 1;
    }

    if (options->lastwriter && options->candldep) {
        printf("[pluto] ERROR: --lastwriter is only supported with --isldep\n");
        pluto_options_free(options);
        usage_message();
        return 1;
    }

    if (options->lastwriter && nolastwriter) {
        printf("[pluto] WARNING: both --lastwriter, --nolastwriter are on\n");
        printf("[pluto] disabling --lastwriter\n");
        options->lastwriter = 0;
    }

    if (options->identity == 1) {
        options->partlbtile = 0;
        options->lbtile = 0;
    }

    if (options->partlbtile == 1 && options->lbtile == 0)    {
        options->lbtile = 1;
    }

    if (options->lbtile == 1 && options->tile == 0)    {
        options->tile = 1;
    }

    if (options->multipar == 1 && options->parallel == 0)    {
        fprintf(stdout, "Warning: multipar needs parallel to be on; turning on parallel\n");
        options->parallel = 1;
    }

    if (options->multipar == 1 && options->parallel == 0)    {
        fprintf(stdout, "Warning: multipar needs parallel to be on; turning on parallel\n");
        options->parallel = 1;
    }


    /* Extract polyhedral representation */
    PlutoProg *prog = NULL; 

    osl_scop_p scop = NULL;
    char *irroption = NULL;

    /* Extract polyhedral representation from clan scop */
    if(!strcmp(srcFileName, "stdin")){  //read from stdin
        src_fp = stdin;
        osl_interface_p registry = osl_interface_get_default_registry();
        t_start = rtclock();
        scop = osl_scop_pread(src_fp, registry, PLUTO_OSL_PRECISION);
        t_d = rtclock() - t_start;
    }else{  // read from regular file

      src_fp  = fopen(srcFileName, "r");

      if (!src_fp)   {
          fprintf(stderr, "pluto: error opening source file: '%s'\n", srcFileName);
          pluto_options_free(options);
          return 6;
      }

      clan_options_p clanOptions = clan_options_malloc();

      if (options->readscop){
          osl_interface_p registry = osl_interface_get_default_registry();
          t_start = rtclock();
          scop = osl_scop_pread(src_fp, registry, PLUTO_OSL_PRECISION);
          t_d = rtclock() - t_start;
      }else{
          t_start = rtclock();
          scop = clan_scop_extract(src_fp, clanOptions);
          t_d = rtclock() - t_start;
      }

      if (!scop || !scop->statement)   {
          fprintf(stderr, "Error extracting polyhedra from source file: \'%s'\n",
                  srcFileName);
          pluto_options_free(options);
          return 8;
      }
      FILE *srcfp = fopen(".srcfilename", "w");
      if (srcfp)    {
          fprintf(srcfp, "%s\n", srcFileName);
          fclose(srcfp);
      }

      clan_options_free(clanOptions);

      /* IF_DEBUG(clan_scop_print_dot_scop(stdout, scop, clanOptions)); */
    }

    /* Convert clan scop to Pluto program */
    prog = scop_to_pluto_prog(scop, options);

    /* Backup irregular program portion in .scop. */
    osl_irregular_p irreg_ext = NULL;
    irreg_ext = osl_generic_lookup(scop->extension, OSL_URI_IRREGULAR);
    if(irreg_ext!=NULL)
      irroption = osl_irregular_sprint(irreg_ext);  //TODO: test it
    osl_irregular_free(irreg_ext);

    IF_MORE_DEBUG(pluto_prog_print(stdout, prog));

    int dim_sum=0;
    for (i=0; i<prog->nstmts; i++) {
        dim_sum += prog->stmts[i]->dim;
    }

   
    if (!options->silent)   {
        fprintf(stdout, "[pluto] Number of statements: %d\n", prog->nstmts);
        fprintf(stdout, "[pluto] Total number of loops: %d\n", dim_sum);
        fprintf(stdout, "[pluto] Number of deps: %d\n", prog->ndeps);
        fprintf(stdout, "[pluto] Maximum domain dimensionality: %d\n", prog->nvar);
        fprintf(stdout, "[pluto] Number of parameters: %d\n", prog->npar);
    }

    if (options->iss) {
        // PlutoConstraints *dom = pluto_constraints_read(stdin);
        // printf("Input set\n");
        // pluto_constraints_compact_print(stdout, dom);
        // PlutoConstraints **doms = malloc(1*sizeof(PlutoConstraints *));
        // doms[0] = dom;
        // pluto_find_iss(doms, 1, 1, NULL);
        // PlutoMatrix *mat = pluto_matrix_input(stdin);
        // pluto_constraints_print(stdout, dom);
        // pluto_matrix_print(stdout, mat);
        // PlutoConstraints *farkas = farkas_affine(dom, mat);
        //pluto_constraints_pretty_print(stdout, farkas);
        // pluto_constraints_free(dom);
        // pluto_options_free(options);
        pluto_iss_dep(prog);
    }

    // writePolyhedralModelToFile("original_polyhedral_model.txt",prog);



    t_start = rtclock();
    /* Auto transformation */
    if (!options->identity) {
        //pluto_auto_transform(prog);
            int i, j, s, nsols, conc_start_found, depth;
    /* The maximum number of linearly independent solutions needed across all
     * statements */
    int num_ind_sols_req;

    /* The number of linearly independent solutions found (max across all
     * statements) */
    int num_ind_sols_found;
    /* Pluto algo mode -- LAZY or EAGER */
    bool hyp_search_mode;

    Stmt **stmts = prog->stmts;
    int nstmts = prog->nstmts;

    for (i=0; i<prog->ndeps; i++) {
        prog->deps[i]->satisfied = false;
    }

    /* Create the data dependence graph */
    prog->ddg = ddg_create(prog);
    ddg_compute_scc(prog);

    Graph *ddg = prog->ddg;
    int nvar = prog->nvar;
    int npar = prog->npar;

    if (nstmts == 0)  return 0;

    PlutoMatrix **orig_trans = malloc(nstmts*sizeof(PlutoMatrix *));
    PlutoHypType **orig_hyp_types = malloc(nstmts*sizeof(PlutoHypType *));
    int orig_num_hyperplanes = prog->num_hyperplanes;
    HyperplaneProperties *orig_hProps = prog->hProps;

    /* Get rid of any existing transformation */
    for (i=0; i<nstmts; i++) {
        Stmt *stmt = prog->stmts[i];
        /* Save the original transformation */
        orig_trans[i] = stmt->trans;
        //printf("stmt->trans size:%d,%d",orig_trans[i]->nrows,orig_trans[i]->ncols);
        orig_hyp_types[i] = stmt->hyp_types;
        /* Pre-allocate a little more to prevent frequent realloc */
        stmt->trans = pluto_matrix_alloc(2*stmt->dim+1, stmt->dim+npar+1);
        stmt->trans->nrows = 0;
        stmt->hyp_types = NULL;
    }

    normalize_domains(prog);

    hyp_search_mode = EAGER;

    prog->num_hyperplanes = 0;
    prog->hProps = NULL;

    /* The number of independent solutions required for the deepest 
     * statement */
    num_ind_sols_req = 0;
    for (i=0; i<nstmts; i++)    {
        num_ind_sols_req = PLMAX(num_ind_sols_req, stmts[i]->dim);
    }

    depth = 0;

    if (precut(prog, ddg, depth))   {
        /* Distributed based on .fst or .precut file (customized user-supplied
         * fusion structure */
        num_ind_sols_found = pluto_get_max_ind_hyps(prog);
        printf("[pluto] Forced custom fusion structure from .fst/.precut\n");
        IF_DEBUG(fprintf(stdout, "%d ind solns in .precut file\n", 
                    num_ind_sols_found));
    }else{
        num_ind_sols_found = 0;
        if (options->fuse == SMART_FUSE)    {
            cut_scc_dim_based(prog,ddg);
        }
    }


    /* For diamond tiling */
    conc_start_found = 0;

    do{
        /* Number of linearly independent solutions remaining to be found
         * (maximum across all statements) */
        int num_sols_left;

        if (options->fuse == NO_FUSE)   {
            ddg_compute_scc(prog);
            cut_all_sccs(prog, ddg);
        }

        num_sols_left = 0;
        for (s=0; s<nstmts; s++) {
            /* Num linearly independent hyperplanes remaining to be
             * found for a statement; take max across all */
            num_sols_left = PLMAX(num_sols_left, stmts[s]->dim_orig
                    - pluto_stmt_get_num_ind_hyps(stmts[s]));
            printf("stmts[%d]->dim_orig:%d\n pluto_stmt_get_num_ind_hyps(stmts[%d]):%d\n",s,stmts[s]->dim_orig,s,pluto_stmt_get_num_ind_hyps(stmts[s]));        
        }


        /* Progress in the EAGER mode is made every time a solution is found;
         * thus, the maximum number of linearly independent solutions
         * remaining to be found is the difference between the number required
         * for the deepest statement and the number found so far for the
         * deepest statement (since in EAGER mode, if there was a statement
         * that had fewer than num_ind_sols_found linearly independent hyperplanes,
         * it means it didn't need that many hyperplanes and all of its
         * linearly independent solutions had been found */
        printf("num_ind_sols_req%d\n",num_ind_sols_req);
        printf("num_ind_sols_found%d\n",num_ind_sols_found);
        printf("num_sols_left%d\n",num_sols_left);
        assert(hyp_search_mode == LAZY || num_sols_left == num_ind_sols_req - num_ind_sols_found);

            
        nsols = find_permutable_hyperplanes(prog, hyp_search_mode,
                num_sols_left, depth);
        printf("nsols%d\n",nsols);
        num_sols_left = num_sols_left-nsols;
        printf("%d num_sols_left after num_sols_left = num_sols_left-nsols",num_sols_left);      
        num_ind_sols_found = pluto_get_max_ind_hyps(prog);
        IF_DEBUG(fprintf(stdout, "[pluto] pluto_auto_transform: band level %d; %d hyperplane(s) found\n",
                    depth, nsols));
        IF_DEBUG2(pluto_transformations_pretty_print(prog));

        if(options->ifreplace ==1 && num_sols_left==0){
            PlutoMatrix *matrix = read_schedule(inputfilename);
            if (matrix ==NULL){
                printf("read_schedule is erro");
            }
            else
                for (int i = 0; i < matrix->nrows; i++) {
                    for (int j = 0; j < matrix->ncols; j++) {
                        printf("%d ", matrix->val[i][j]);
                        }
                        printf("\n");
                }
            options->ifreplace =0;
            //对转换矩阵进行更新替代
                for(int J=0;J<nstmts;J++){
                    int numscalar = 0;  
                    for(int I=0;I<stmts[J]->trans->nrows;I++){
                        if(stmts[J]->hyp_types[I]== H_SCALAR){
                            numscalar++;   
                        }else{
                            for(int K=0;K<nvar+npar+1;K++){
                                stmts[J]->trans->val[I][K] = matrix->val[I-numscalar][J*(nvar+npar+1)+K];
                            }
                        }
                    }
                }
                for (int Q = 0; Q < matrix->nrows; Q++) {
                    free(matrix->val[Q]);
                }
                free(matrix->val);
                matrix->val =NULL;
        }

        if (nsols >= 1) {
            /* Diamond tiling: done for the first band of permutable loops */
            if (options->lbtile && nsols >= 2 && !conc_start_found) {
                conc_start_found = pluto_diamond_tile(prog);
            }

            for (j=0; j<nsols; j++)      {
                /* Mark dependences satisfied by this solution */
                dep_satisfaction_update(prog, stmts[0]->trans->nrows - nsols + j);
                ddg_update(ddg, prog);
            }
        }else{
            /* Satisfy inter-scc dependences via distribution since we have 
             * no more fusable loops */

            ddg_compute_scc(prog);

            if (get_num_unsatisfied_inter_scc_deps(prog) >= 1) {
                if (options->fuse == NO_FUSE)  {
                    /* No fuse */
                    cut_all_sccs(prog, ddg);
                }else if (options->fuse == SMART_FUSE)  {
                    /* Smart fuse (default) */
                    cut_smart(prog, ddg);
                }else{
                    /* Max fuse */
                    if (depth >= 2*nvar+1) cut_all_sccs(prog, ddg);
                    else cut_conservative(prog, ddg);
                }
            }else{
                /* Only one SCC or multiple SCCs with no unsatisfied inter-SCC
                 * deps, and no solutions found  */
                if (hyp_search_mode == EAGER)   {
                    IF_DEBUG(printf("[pluto] Switching to LAZY mode\n"););
                    hyp_search_mode = LAZY;
                }else if (!deps_satisfaction_check(prog)) {
                    assert(hyp_search_mode == LAZY);
                    /* There is a problem; solutions should have been found if
                     * there were no inter-scc deps, and some unsatisfied deps
                     * existed */
                    if (options->debug || options->moredebug) {
                        printf("\tNumber of unsatisfied deps: %d\n",
                                get_num_unsatisfied_deps(prog->deps, prog->ndeps));
                        printf("\tNumber of unsatisfied inter-scc deps: %d\n",
                                get_num_unsatisfied_inter_scc_deps(prog));
                        fprintf(stdout, "[pluto] WARNING: Unfortunately, pluto cannot find any more hyperplanes.\n");
                        fprintf(stdout, "\tThis is usually a result of (1) a bug in the dependence tester,\n");
                        fprintf(stdout, "\tor (2) a bug in Pluto's auto transformation,\n");
                        fprintf(stdout, "\tor (3) an inconsistent .fst/.precut in your working directory.\n");
                        fprintf(stdout, "\tTransformation found so far:\n");
                        pluto_transformations_pretty_print(prog);
                        pluto_compute_dep_directions(prog);
                        pluto_compute_dep_satisfaction(prog);
                        pluto_print_dep_directions(prog);
                    }
                    denormalize_domains(prog);
                    printf("[pluto] WARNING: working with original (identity) transformation (if they exist)\n");
                    /* Restore original ones */
                    for (i=0; i<nstmts; i++) {
                        stmts[i]->trans = orig_trans[i];
                        stmts[i]->hyp_types = orig_hyp_types[i];
                        prog->num_hyperplanes = orig_num_hyperplanes;
                        prog->hProps = orig_hProps;
                    }
                    return 1;
                }
            }
        }
        /* Under LAZY mode, do a complex dep satisfaction check to take 
         * care of partial satisfaction (rarely needed) */
        if (hyp_search_mode == LAZY) pluto_compute_dep_satisfaction_complex(prog);
        depth++;

    }while (!pluto_transformations_full_ranked(prog) || 
            !deps_satisfaction_check(prog));

    if (options->lbtile && !conc_start_found) {
        PLUTO_MESSAGE(printf("[pluto] Diamond tiling not possible/useful\n"););
    }

    denormalize_domains(prog);

    for (i=0; i<nstmts; i++)    {
        pluto_matrix_free(orig_trans[i]);
        free(orig_hyp_types[i]);
    }
    free(orig_trans);
    free(orig_hyp_types);
    free(orig_hProps);

    IF_DEBUG(printf("[pluto] pluto_auto_transform: successful, done\n"););

    }
    t_t = rtclock() - t_start;

    pluto_detect_transformation_properties(prog);

    if (!options->silent)   {
        fprintf(stdout, "[pluto] Affine transformations [<iter coeff's> <param> <const>]\n\n");
        /* Print out transformations */
        pluto_transformations_pretty_print(prog);

        pluto_print_hyperplane_properties(prog);
    }
    if(inputfilename!=NULL){
    char *inputfilename_no_ext = strdup(inputfilename);
    if (strlen(inputfilename_no_ext) > 4 && !strcmp(inputfilename_no_ext + strlen(inputfilename_no_ext) - 4, ".txt")) {
        inputfilename_no_ext[strlen(inputfilename_no_ext) - 4] = '\0'; // 去除 ".txt" 后缀
    }

    // 创建新的文件名，包含 inputfilename 的基本名称
    char newFileName[256];
    sprintf(newFileName, "%s_polyhedral_model.txt", inputfilename_no_ext);

    // 调用函数并传入新的文件名
    writePolyhedralModelToFile(newFileName, prog);

    // 释放复制的字符串
    free(inputfilename_no_ext);
    }else{
        char newFileName[256];
        strcpy(newFileName, srcFileName);

        size_t len = strlen(newFileName);

        // 如果文件名以 ".c" 结尾，则去掉 ".c"
        if (len > 2 && !strcmp(newFileName + len - 2, ".c")) {
            newFileName[len - 2] = '\0';
        }

        // 拼接 "_polyhedral_model.txt"
        sprintf(newFileName, "%s_polyhedral_model.txt", newFileName);

        // 传递给函数
        writePolyhedralModelToFile(newFileName, prog);
    }

    if (options->tile)   {
        pluto_tile(prog);
    }else{
        if (options->intratileopt) {
            pluto_intra_tile_optimize(prog, 0);
        }
    }

    if (options->parallel && !options->tile && !options->identity)   {
        /* Obtain wavefront/pipelined parallelization by skewing if
         * necessary */
        int nbands;
        Band **bands;
        bands = pluto_get_outermost_permutable_bands(prog, &nbands);
        bool retval = pluto_create_tile_schedule(prog, bands, nbands);
        pluto_bands_free(bands, nbands);

        /* If the user hasn't supplied --tile and there is only pipelined
         * parallelism, we will warn the user */
        if (retval)   {
            printf("[pluto] WARNING: pipelined parallelism exists and --tile is not used.\n");
            printf("use --tile for better parallelization \n");
            IF_DEBUG(fprintf(stdout, "[pluto] After skewing:\n"););
            IF_DEBUG(pluto_transformations_pretty_print(prog););
            IF_DEBUG(pluto_print_hyperplane_properties(prog););
        }
    }

    if (options->unroll || options->polyunroll)    {
        /* Will generate a .unroll file */
        /* plann/plorc needs a .params */
        FILE *paramsFP = fopen(".params", "w");
        if (paramsFP)   {
            int i;
            for (i=0; i<prog->npar; i++)  {
                fprintf(paramsFP, "%s\n", prog->params[i]);
            }
            fclose(paramsFP);
        }
        pluto_detect_mark_unrollable_loops(prog);
    }

    if (options->polyunroll)    {
        /* Experimental */
        for (i=0; i<prog->num_hyperplanes; i++)   {
            if (prog->hProps[i].unroll)  {
                unroll_phis(prog, i, options->ufactor);
            }
        }
    }

    if(!strcmp(srcFileName, "stdin")){  
        //input stdin == output stdout
        pluto_populate_scop(scop, prog, options);
        osl_scop_print(stdout, scop);
    }else{  // do the usual Pluto stuff
  
      /* NO MORE TRANSFORMATIONS BEYOND THIS POINT */
      /* Since meta info about loops
       * is printed to be processed by scripts - if transformations are
       * performed, changed loop order/iterator names will be missed  */
      gen_unroll_file(prog);

      char *outFileName;
      char *cloogFileName;
      if (options->out_file == NULL)  {
        /* Get basename, remove .c extension and append a new one */
        char *basec, *bname;
        basec = strdup(srcFileName);
        bname = basename(basec);
        if(inputfilename !=NULL){
            inputfilename[strlen(inputfilename)-4]='\0';
            outFileName = alloca(strlen(bname)+strlen(inputfilename)+strlen(".pluto.c")+1);
            cloogFileName = alloca(strlen(bname)+strlen(inputfilename)+strlen(".pluto.cloog")+1);
            if (strlen(bname) >= 2 && !strcmp(bname+strlen(bname)-2, ".c")) {
                strncpy(outFileName, bname, strlen(bname)-2);
                strncpy(cloogFileName, bname, strlen(bname)-2);
                outFileName[strlen(bname)-2] = '\0';
                cloogFileName[strlen(bname)-2] = '\0';
                strcat(outFileName,inputfilename);
                strcat(cloogFileName,inputfilename);
            }else{
                strcpy(outFileName, bname);
                strcat(outFileName,inputfilename);
                strcpy(cloogFileName, bname);
                strcat(cloogFileName,inputfilename);
            }
        }else{
        /* max size when tiled.* */
            outFileName = alloca(strlen(bname)+strlen(".pluto.c")+1);
            cloogFileName = alloca(strlen(bname)+strlen(".pluto.cloog")+1);
            if (strlen(bname) >= 2 && !strcmp(bname+strlen(bname)-2, ".c")) {
                strncpy(outFileName, bname, strlen(bname)-2);
                strncpy(cloogFileName, bname, strlen(bname)-2);
                outFileName[strlen(bname)-2] = '\0';
                cloogFileName[strlen(bname)-2] = '\0';
                
            }else{
                strcpy(outFileName, bname);
                strcpy(cloogFileName, bname);
                }
        }
        strcat(outFileName, ".pluto.c");
        free(basec);
    }else{
          outFileName = options->out_file;
          cloogFileName = alloca(strlen(options->out_file)+1);
          strcpy(cloogFileName, options->out_file);
      }

  
      strcat(cloogFileName, ".pluto.cloog");
  
      cloogfp = fopen(cloogFileName, "w+");
      if (!cloogfp)   {
          fprintf(stderr, "[Pluto] Can't open .cloog file: '%s'\n", cloogFileName);
          pluto_options_free(options);
          pluto_prog_free(prog);
          return 9;
      }
  
      outfp = fopen(outFileName, "w");
      if (!outfp) {
          fprintf(stderr, "[Pluto] Can't open file '%s' for writing\n", outFileName);
          pluto_options_free(options);
          pluto_prog_free(prog);
          fclose(cloogfp);
          return 10;
      }
  
      /* Generate .cloog file */
      pluto_gen_cloog_file(cloogfp, prog);
      /* Add the <irregular> tag from clan, if any */
      if (irroption != NULL) {
          fprintf(cloogfp, "<irregular>\n%s\n</irregular>\n\n", irroption);
          free(irroption);
      }
  
      rewind(cloogfp);
  
    
      /* Generate code using Cloog and add necessary stuff before/after code */
      t_start = rtclock();
      pluto_multicore_codegen(cloogfp, outfp, prog);
      t_c = rtclock() - t_start;

      FILE *tmpfp = fopen(".outfilename", "w");

      if (tmpfp)    {
          fprintf(tmpfp, "%s\n", outFileName);
          fclose(tmpfp);
          PLUTO_MESSAGE(printf( "[Pluto] Output written to %s\n", outFileName););
      }
  
      fclose(cloogfp);
      fclose(outfp);

    }

    t_all = rtclock() - t_start_all;

    if (options->time && !options->silent) {
        printf("\n[pluto] Timing statistics\n[pluto] SCoP extraction + dependence analysis time: %0.6lfs\n", t_d);
        printf("[pluto] Auto-transformation time: %0.6lfs\n", t_t);
        printf("[pluto] Code generation time: %0.6lfs\n", t_c);
        printf("[pluto] Other/Misc time: %0.6lfs\n", t_all-t_c-t_t-t_d);
        printf("[pluto] Total time: %0.6lfs\n", t_all);
        printf("[pluto] All times: %0.6lf %0.6lf %.6lf %.6lf\n", t_d, t_t, t_c,
             t_all-t_c-t_t-t_d);
    }


    pluto_prog_free(prog);


    pluto_options_free(options);

    osl_scop_free(scop);
    
    return 0;
}
