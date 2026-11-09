set terminal png medium
set output "graph.png"

set title "PyLinda Message Rates"
set xlabel "seconds since server start"
set ylabel "message/s"

plot "lindamon-py.txt" using 1:2 title "Plain" with lines, \
     "lindamon-iso.txt" using 1:2 title "Isomorphism" with lines, \
     "lindamon-c.txt" using 1:2 title "C Client" with lines, \
     x*10+1 title "Ideal" with lines

